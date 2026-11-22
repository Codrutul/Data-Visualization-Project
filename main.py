import json
from pathlib import Path

import altair as alt
import pandas as pd
from altair.datasets import data


STATE_INFO = {
    'AL': ('Alabama', 1), 'AK': ('Alaska', 2), 'AZ': ('Arizona', 4),
    'AR': ('Arkansas', 5), 'CA': ('California', 6), 'CO': ('Colorado', 8),
    'CT': ('Connecticut', 9), 'DE': ('Delaware', 10), 'FL': ('Florida', 12),
    'GA': ('Georgia', 13), 'HI': ('Hawaii', 15), 'ID': ('Idaho', 16),
    'IL': ('Illinois', 17), 'IN': ('Indiana', 18), 'IA': ('Iowa', 19),
    'KS': ('Kansas', 20), 'KY': ('Kentucky', 21), 'LA': ('Louisiana', 22),
    'ME': ('Maine', 23), 'MD': ('Maryland', 24), 'MA': ('Massachusetts', 25),
    'MI': ('Michigan', 26), 'MN': ('Minnesota', 27), 'MS': ('Mississippi', 28),
    'MO': ('Missouri', 29), 'MT': ('Montana', 30), 'NE': ('Nebraska', 31),
    'NV': ('Nevada', 32), 'NH': ('New Hampshire', 33), 'NJ': ('New Jersey', 34),
    'NM': ('New Mexico', 35), 'NY': ('New York', 36), 'NC': ('North Carolina', 37),
    'ND': ('North Dakota', 38), 'OH': ('Ohio', 39), 'OK': ('Oklahoma', 40),
    'OR': ('Oregon', 41), 'PA': ('Pennsylvania', 42), 'RI': ('Rhode Island', 44),
    'SC': ('South Carolina', 45), 'SD': ('South Dakota', 46), 'TN': ('Tennessee', 47),
    'TX': ('Texas', 48), 'UT': ('Utah', 49), 'VT': ('Vermont', 50),
    'VA': ('Virginia', 51), 'WA': ('Washington', 53),
    'WV': ('West Virginia', 54), 'WI': ('Wisconsin', 55), 'WY': ('Wyoming', 56),
    'DC': ('District of Columbia', 11),
}

# Count only US facilities with a recognizable state or district in the source data.
data_path = Path(__file__).resolve().parent / 'data' / 'datacenters.csv'
facilities = pd.read_csv(data_path)
required_columns = {'state', 'country'}
missing_columns = required_columns - set(facilities.columns)
if missing_columns:
    raise ValueError(f'Missing required columns in {data_path}: {sorted(missing_columns)}')

us_facilities = facilities[
    facilities['country'].astype('string').str.strip().str.casefold().eq('united states')
].copy()
state_lookup = {
    value.casefold(): abbreviation
    for abbreviation, (name, _) in STATE_INFO.items()
    for value in (abbreviation, name)
}
state_values = us_facilities['state'].astype('string').str.strip()
us_facilities['state_abbr'] = state_values.str.casefold().map(state_lookup)

# Some rows append a state abbreviation to a metro or city name (for example, "Kansas City MO").
state_suffix = state_values.str.extract(r'(?i)\b([A-Z]{2})\s*$')[0].str.upper()
us_facilities['state_abbr'] = us_facilities['state_abbr'].fillna(
    state_suffix.where(state_suffix.isin(STATE_INFO))
)
counts = us_facilities['state_abbr'].value_counts()

df = pd.DataFrame([
    {
        'state_id': fips,
        'state_name': name,
        'data_center_count': int(counts.get(abbr, 0)),
    }
    for abbr, (name, fips) in STATE_INFO.items()
]).sort_values('state_name').reset_index(drop=True)

land_price_path = Path(__file__).resolve().parent / 'data' / 'land_price.csv'
land_prices = pd.read_csv(land_price_path, sep=';')
land_price_columns = {'Year', 'Geo Level', 'State ANSI', 'Value'}
missing_land_price_columns = land_price_columns - set(land_prices.columns)
if missing_land_price_columns:
    raise ValueError(
        f'Missing required columns in {land_price_path}: {sorted(missing_land_price_columns)}'
    )

latest_land_price_year = int(land_prices['Year'].max())
latest_land_prices = land_prices.loc[
    land_prices['Year'].eq(latest_land_price_year)
    & land_prices['Geo Level'].astype('string').str.strip().str.upper().eq('STATE')
].copy()
latest_land_prices['state_id'] = pd.to_numeric(
    latest_land_prices['State ANSI'], errors='coerce'
)
def parse_land_price(value):
    value = str(value).strip()
    if ',' in value:
        # The source expresses thousands of dollars with a decimal comma (e.g. 4,25 = $4,250).
        return float(value.replace(',', '.')) * 1000
    return float(value)


latest_land_prices['land_price'] = latest_land_prices['Value'].map(parse_land_price)
latest_land_prices = latest_land_prices.loc[
    latest_land_prices['state_id'].isin(df['state_id']),
    ['state_id', 'land_price'],
]
if latest_land_prices['state_id'].duplicated().any():
    raise ValueError(f'Duplicate state land prices found for {latest_land_price_year}')

df = df.merge(latest_land_prices, on='state_id', how='left', validate='one_to_one')
df['state_id'] = df['state_id'].astype(int)
df['land_price_is_estimate'] = False
df['land_price_note'] = 'Reported in land_price.csv'

# The source omits Alaska and Hawaii. Use transparent proxy estimates for map visibility.
proxy_state_ids = {
    2: 30,  # Alaska from Montana
    15: 6,  # Hawaii from California
}
state_name_by_id = {fips: name for name, fips in STATE_INFO.values()}
for state_id, proxy_state_id in proxy_state_ids.items():
    proxy_price = df.loc[df['state_id'].eq(proxy_state_id), 'land_price']
    if proxy_price.empty or pd.isna(proxy_price.iloc[0]):
        raise ValueError(f'Cannot estimate {state_name_by_id[state_id]}: proxy value is missing')
    df.loc[df['state_id'].eq(state_id), 'land_price'] = float(proxy_price.iloc[0])
    df.loc[df['state_id'].eq(state_id), 'land_price_is_estimate'] = True
    df.loc[df['state_id'].eq(state_id), 'land_price_note'] = (
        f'Estimate based on {state_name_by_id[proxy_state_id]}'
    )

electricity_path = Path(__file__).resolve().parent / 'data' / 'electricity_price.csv'
electricity = pd.read_csv(electricity_path, sep=';', header=None, skiprows=3, dtype='string')
if electricity.shape[1] != 10:
    raise ValueError(f'Expected 10 columns in {electricity_path}, found {electricity.shape[1]}')
electricity.columns = [
    'year', 'state', 'commercial_revenue', 'commercial_sales', 'commercial_customers',
    'commercial_price', 'industrial_revenue', 'industrial_sales', 'industrial_customers',
    'industrial_price',
]
electricity = electricity.loc[electricity['state'].isin(STATE_INFO)].copy()
electricity['state_id'] = electricity['state'].map(
    {abbreviation: fips for abbreviation, (_, fips) in STATE_INFO.items()}
)
electricity['electricity_price'] = pd.to_numeric(
    electricity['commercial_price'].str.replace(',', '.', regex=False),
    errors='raise',
)
electricity['electricity_price_year'] = pd.to_numeric(electricity['year'], errors='raise')
latest_electricity_year = int(electricity['electricity_price_year'].max())
electricity = electricity.loc[
    electricity['electricity_price_year'].eq(latest_electricity_year),
    ['state_id', 'electricity_price'],
]
if electricity['state_id'].duplicated().any():
    raise ValueError(f'Duplicate commercial electricity prices found for {latest_electricity_year}')

df = df.merge(electricity, on='state_id', how='left', validate='one_to_one')

population_path = Path(__file__).resolve().parent / 'data' / 'population.csv'
population_rows = pd.read_csv(
    population_path,
    sep=';',
    header=None,
    skiprows=3,
    usecols=[0, 1],
    names=['area', 'population'],
    dtype='string',
    on_bad_lines='skip',
)
population_rows = population_rows.loc[
    population_rows['area'].str.startswith('.', na=False)
    & population_rows['population'].notna()
].copy()
population_rows['state_name'] = population_rows['area'].str.lstrip('.').str.strip()
population_rows['state_id'] = population_rows['state_name'].str.casefold().map(
    {name.casefold(): fips for name, fips in STATE_INFO.values()}
)
population_rows = population_rows.loc[
    population_rows['state_id'].notna(),
    ['state_id', 'population'],
].copy()
population_rows['state_id'] = population_rows['state_id'].astype(int)
population_rows['population'] = pd.to_numeric(
    population_rows['population'].str.replace('.', '', regex=False),
    errors='raise',
)
population_year = 2025
if population_rows['state_id'].duplicated().any():
    raise ValueError(f'Duplicate state population estimates found in {population_path}')
df = df.merge(population_rows, on='state_id', how='left', validate='one_to_one')
missing_population_ids = sorted(set(df['state_id']) - set(population_rows['state_id']))
if missing_population_ids:
    missing_population_names = [state_name_by_id[state_id] for state_id in missing_population_ids]
    raise ValueError(
        f'Missing population estimates in {population_path}: {missing_population_names}'
    )

county_path = Path(__file__).resolve().parent / 'data' / 'laucnty25.csv'
county_unemployment = pd.read_csv(
    county_path,
    sep=';',
    skiprows=1,
    usecols=[
        'State FIPS Code',
        'County FIPS Code',
        'County Name/State Abbreviation',
        'Labor Force',
        'Unemployed',
        'Unemployment Rate (%)',
    ],
    dtype='string',
)
county_unemployment = county_unemployment.loc[
    county_unemployment['State FIPS Code'].str.fullmatch(r'\d{2}', na=False)
    & county_unemployment['County FIPS Code'].str.fullmatch(r'\d{3}', na=False)
].copy()
county_unemployment['state_id'] = pd.to_numeric(
    county_unemployment['State FIPS Code'],
    errors='raise',
)
county_unemployment = county_unemployment.loc[
    county_unemployment['state_id'].isin(df['state_id'])
].copy()
county_unemployment['county_id'] = pd.to_numeric(
    county_unemployment['State FIPS Code'] + county_unemployment['County FIPS Code'],
    errors='raise',
)
county_unemployment['unemployment_rate'] = pd.to_numeric(
    county_unemployment['Unemployment Rate (%)'].str.strip().str.replace(
        ',', '.', regex=False
    ),
    errors='raise',
)
county_unemployment['unemployment_percentile'] = (
    county_unemployment['unemployment_rate'].rank(method='average', pct=True) * 100
)
for column in ('Labor Force', 'Unemployed'):
    county_unemployment[column] = pd.to_numeric(
        county_unemployment[column].str.strip().str.replace('.', '', regex=False),
        errors='raise',
    )
county_unemployment = county_unemployment.rename(columns={
    'County Name/State Abbreviation': 'county_name',
})
if county_unemployment['county_id'].duplicated().any():
    raise ValueError(f'Duplicate county FIPS codes found in {county_path}')
if county_unemployment[
    ['unemployment_rate', 'unemployment_percentile', 'Labor Force', 'Unemployed']
].isna().any().any():
    raise ValueError(f'Missing county unemployment data found in {county_path}')

state_unemployment = county_unemployment.groupby('state_id').agg(
    state_labor_force=('Labor Force', 'sum'),
    state_unemployed=('Unemployed', 'sum'),
)
state_unemployment['unemployment_rate'] = (
    state_unemployment['state_unemployed'] / state_unemployment['state_labor_force'] * 100
)
state_unemployment = state_unemployment[['unemployment_rate']].reset_index()
if set(state_unemployment['state_id']) != set(df['state_id']):
    raise ValueError('County unemployment data does not cover every state in the dashboard')
df = df.merge(state_unemployment, on='state_id', how='left', validate='one_to_one')

atlas_path = Path(__file__).resolve().parent / 'data' / 'compute-atlas-facilities.csv'
atlas = pd.read_csv(atlas_path)
water_path = Path(__file__).resolve().parent / 'data' / 'facility_water_stress.csv'
water_scores = pd.read_csv(water_path, dtype={'id': str})
month_columns = [f'bws_{month:02}_score' for month in range(1, 13)]
water_scores = water_scores.loc[
    water_scores[month_columns].notna().any(axis=1),
    ['id', *month_columns],
].copy()
water_scores['annual_water_stress'] = water_scores[month_columns].mean(axis=1)
water_state_lookup = atlas.loc[
    atlas['facility_type'].eq('data_center') & atlas['state'].isin(STATE_INFO),
    ['id', 'state'],
].copy()
water_state_lookup['state_id'] = water_state_lookup['state'].map(
    {abbreviation: fips for abbreviation, (_, fips) in STATE_INFO.items()}
)
water_state_scores = water_state_lookup.merge(
    water_scores[['id', 'annual_water_stress']],
    on='id',
    how='inner',
    validate='one_to_one',
).groupby('state_id', as_index=False).agg(
    water_stress=('annual_water_stress', 'mean'),
    water_stress_facilities=('annual_water_stress', 'count'),
)
df = df.merge(water_state_scores, on='state_id', how='left', validate='one_to_one')

profile_metrics = [
    ('Data centers', 'data_center_count', 'facilities', None),
    (
        'Land price',
        'land_price',
        f'$/acre ({latest_land_price_year})',
        'land_price_note',
    ),
    (
        'Electricity',
        'electricity_price',
        f'cents/kWh ({latest_electricity_year})',
        None,
    ),
    ('Population', 'population', f'residents ({population_year})', None),
    ('Unemployment', 'unemployment_rate', '%', None),
    ('Water stress', 'water_stress', 'WRI score (0-5)', None),
]
profile_records = []
for category_order, (category, field, unit, note_field) in enumerate(profile_metrics):
    percentile_ranks = df[field].rank(method='average', pct=True) * 100
    for state_index, row in df.iterrows():
        value = row[field]
        missing = pd.isna(value)
        percentile = float(percentile_ranks.iloc[state_index]) if not missing else None
        if missing:
            value_label = 'No data'
            value_note = 'No facility water-stress data available for this state.'
        else:
            if field == 'electricity_price':
                value_label = f'{value:.2f} {unit}'
            elif field == 'unemployment_rate':
                value_label = f'{value:.2f}{unit}'
            elif field == 'water_stress':
                value_label = f'{value:.2f} {unit}'
            else:
                value_label = f'{value:,.0f} {unit}'
            if field == 'water_stress':
                value_note = (
                    f'Average across {int(row["water_stress_facilities"])} facilities '
                    'with WRI scores'
                )
            else:
                value_note = row[note_field] if note_field else 'Reported value'
        profile_records.append({
            'state_id': int(row['state_id']),
            'state_name': row['state_name'],
            'category': category,
            'category_order': category_order,
            'percentile_rank': percentile,
            'value': float(value) if not missing else None,
            'value_label': value_label,
            'value_note': value_note,
        })

profile_df = pd.DataFrame(profile_records)

# Use Compute Atlas for the point layer: it provides facility-level coordinates,
# status, and source links. Limit it to data centers in the 50 states and DC.
point_columns = {
    'id', 'name', 'operator', 'facility_type', 'status', 'confidence', 'city', 'county', 'state',
    'lat', 'lon', 'capacity_operational_mw', 'capacity_planned_mw',
    'source_count', 'detail_url', 'primary_source_url',
}
missing_point_columns = point_columns - set(atlas.columns)
if missing_point_columns:
    raise ValueError(f'Missing required columns in {atlas_path}: {sorted(missing_point_columns)}')

points_df = atlas.loc[
    atlas['facility_type'].eq('data_center')
    & atlas['state'].isin(STATE_INFO),
    list(point_columns),
].copy()
points_df = points_df.rename(columns={
    'lat': 'latitude',
    'lon': 'longitude',
    'operator': 'company',
})
state_ids = {abbreviation: fips for abbreviation, (_, fips) in STATE_INFO.items()}
points_df['state_id'] = points_df['state'].map(state_ids)
if points_df['state_id'].isna().any():
    raise ValueError(f'Unrecognized states found in the Compute Atlas data in {atlas_path}')
points_df['latitude'] = pd.to_numeric(points_df['latitude'], errors='raise')
points_df['longitude'] = pd.to_numeric(points_df['longitude'], errors='raise')
if (
    points_df[['latitude', 'longitude']].isna().any().any()
    or not points_df['latitude'].between(-90, 90).all()
    or not points_df['longitude'].between(-180, 180).all()
):
    raise ValueError(f'Invalid coordinates found in {atlas_path}')

def county_key(names):
    return (
        names.astype('string')
        .str.split(',', n=1).str[0]
        .str.casefold()
        .str.replace(r'\s*\(independent city\)$', ' city', regex=True)
        .str.replace(
            r'\b(county/city|county|parish|borough|census area|municipality)\b',
            ' ',
            regex=True,
        )
        .str.replace(r'[^a-z0-9]+', ' ', regex=True)
        .str.strip()
    )


county_reference = county_unemployment[
    ['county_id', 'state_id', 'county_name']
].copy()
county_reference['county_key'] = county_key(county_reference['county_name'])
if county_reference.duplicated(['state_id', 'county_key']).any():
    raise ValueError('County unemployment reference has ambiguous normalized county names')

atlas_counties = points_df[['id', 'state_id', 'county', 'state']].copy()
atlas_counties['county_key'] = county_key(atlas_counties['county'])
atlas_counties = atlas_counties.merge(
    county_reference[['county_id', 'state_id', 'county_key']],
    on=['state_id', 'county_key'],
    how='left',
    validate='many_to_one',
)

# Connecticut transitioned from counties to planning regions; use legacy county
# FIPS for the county boundaries in the map. La Porte is one word in the LAUS file.
county_fips_aliases = {
    ('CT', 'fairfield'): (9001, 'Fairfield County, CT'),
    ('CT', 'hartford'): (9003, 'Hartford County, CT'),
    ('CT', 'new haven'): (9009, 'New Haven County, CT'),
    ('CT', 'new london'): (9011, 'New London County, CT'),
    ('IN', 'la porte'): (18091, 'LaPorte County, IN'),
}
alias_lookup = {
    (state_ids[state], county): county_id
    for (state, county), (county_id, _) in county_fips_aliases.items()
}
unmatched_counties = atlas_counties['county_id'].isna()
atlas_counties.loc[unmatched_counties, 'county_id'] = [
    alias_lookup.get((state_id, county), pd.NA)
    for state_id, county in zip(
        atlas_counties.loc[unmatched_counties, 'state_id'],
        atlas_counties.loc[unmatched_counties, 'county_key'],
    )
]
unmatched_county_facilities = int(atlas_counties['county_id'].isna().sum())
atlas_county_counts = atlas_counties.dropna(subset=['county_id']).groupby(
    'county_id', as_index=False,
).size().rename(columns={'size': 'data_center_count'})
county_map_data = county_reference[
    ['county_id', 'state_id', 'county_name']
].drop_duplicates('county_id').copy()
missing_alias_rows = [
    {
        'county_id': county_id,
        'state_id': state_ids[state],
        'county_name': county_name,
    }
    for (state, _), (county_id, county_name) in county_fips_aliases.items()
    if county_id not in set(county_map_data['county_id'])
]
if missing_alias_rows:
    county_map_data = pd.concat(
        [county_map_data, pd.DataFrame(missing_alias_rows)],
        ignore_index=True,
    )
county_map_data = county_map_data.merge(
    atlas_county_counts,
    on='county_id',
    how='left',
    validate='one_to_one',
)
county_map_data['data_center_count'] = county_map_data['data_center_count'].fillna(0).astype(int)
county_map_data['state_name'] = county_map_data['state_id'].map(
    {state_id: name for name, state_id in STATE_INFO.values()}
)
county_max_count = int(county_map_data['data_center_count'].max())
overview_points_df = atlas.loc[
    atlas['facility_type'].isin(['data_center', 'power_generation', 'crypto_mining'])
    & atlas['state'].isin(STATE_INFO),
    list(point_columns),
].copy().rename(columns={
    'lat': 'latitude',
    'lon': 'longitude',
    'operator': 'company',
})
overview_points_df['state_id'] = overview_points_df['state'].map(state_ids)
overview_points_df['latitude'] = pd.to_numeric(overview_points_df['latitude'], errors='raise')
overview_points_df['longitude'] = pd.to_numeric(overview_points_df['longitude'], errors='raise')
if (
    overview_points_df[['latitude', 'longitude']].isna().any().any()
    or not overview_points_df['latitude'].between(-90, 90).all()
    or not overview_points_df['longitude'].between(-180, 180).all()
):
    raise ValueError(f'Invalid coordinates found in {atlas_path}')

# Precomputed point-in-polygon join against WRI Aqueduct 4.0 baseline monthly basins.
water_profiles_json = water_scores.set_index('id')[month_columns].to_json(orient='index')

status_domain = ['operational', 'under_construction', 'permitted', 'proposed', 'cancelled']
unknown_statuses = sorted(set(overview_points_df['status'].dropna()) - set(status_domain))
if unknown_statuses:
    raise ValueError(f'Unrecognized facility statuses in {atlas_path}: {unknown_statuses}')
if overview_points_df['status'].isna().any():
    raise ValueError(f'Missing facility statuses found in {atlas_path}')
facility_type_domain = sorted(overview_points_df['facility_type'].dropna().unique())
facility_type_options_json = json.dumps([
    {'value': facility_type, 'label': facility_type.replace('_', ' ').title()}
    for facility_type in facility_type_domain
])
facility_status_options_json = json.dumps([
    {'value': status, 'label': status.replace('_', ' ').title()}
    for status in status_domain
])

show_points = alt.param(
    name='show_points',
    value=False,
)
facility_types = alt.param(name='facility_types', value=['data_center'])
facility_statuses = alt.param(name='facility_statuses', value=[])
map_zoom = alt.param(name='overview_zoom', value=1)
map_pan_x = alt.param(name='overview_pan_x', value=0)
map_pan_y = alt.param(name='overview_pan_y', value=0)
map_metric = alt.param(
    name='map_metric',
    value='Data center count',
)
map_granularity = alt.param(
    name='map_granularity',
    value='state',
)
metric_value_expression = (
    "map_metric === 'Land price' ? datum.land_price : "
    "map_metric === 'Commercial electricity price' ? datum.electricity_price : "
    "map_metric === 'Population' ? datum.population : "
    "map_metric === 'Water stress' ? datum.water_stress : "
    "datum.data_center_count"
)
metric_color_scheme = alt.ExprRef(
    expr=(
        "map_metric === 'County unemployment rate' ? 'oranges' : "
        "map_metric === 'Land price' ? 'greens' : "
        "map_metric === 'Commercial electricity price' ? 'oranges' : "
        "map_metric === 'Population' ? 'purples' : "
        "map_metric === 'Water stress' ? 'purples' : 'blues'"
    )
)
metric_color = alt.Color(
    'metric_value:Q',
    title='Selected map metric',
    scale=alt.Scale(scheme=metric_color_scheme),
    legend=None,
)

# Load the US states topology and select states by their FIPS IDs.
states = alt.topo_feature(data.us_10m.url, 'states')
click = alt.selection_point(
    name='selected_state',
    fields=['state_id'],
    clear=False,
    on=alt.EventStream(type='click', filter='false'),
)
selected_state_predicate = {'param': 'selected_state'}

state_layer = alt.Chart(states, name='overview_state_shapes').mark_geoshape(
    clip=True,
    strokeWidth=0.5,
).encode(
    color=metric_color,
    stroke=alt.condition(
        click,
        alt.value('white'),
        alt.value('#111111'),
        empty=False,
    ),
    opacity=alt.condition(
        click,
        alt.value(1),
        alt.value(0.12),
    ),
    tooltip=[
        alt.Tooltip('state_name:N', title='State'),
        alt.Tooltip('data_center_count:Q', title='Data centers', format=','),
        alt.Tooltip(
            'electricity_price:Q',
            title=f'Commercial electricity price (cents/kWh, {latest_electricity_year})',
            format='.2f',
        ),
        alt.Tooltip(
            'population:Q',
            title=f'Population estimate ({population_year})',
            format=',',
        ),
        alt.Tooltip(
            'unemployment_rate:Q',
            title='Weighted unemployment rate (2025)',
            format='.2f',
        ),
    ],
).transform_lookup(
    lookup='id',
    from_=alt.LookupData(
        df,
        'state_id',
        [
            'state_id',
            'state_name',
            'data_center_count',
            'land_price',
            'land_price_is_estimate',
            'land_price_note',
            'electricity_price',
            'population',
            'unemployment_rate',
            'water_stress',
        ],
    ),
).transform_calculate(
    metric_value=metric_value_expression,
).transform_filter(
    "map_metric !== 'County unemployment rate' && "
    "!(map_metric === 'Data center count' && map_granularity === 'county')"
).add_params(
    click
)

counties = alt.topo_feature(data.us_10m.url, 'counties')
county_layer = alt.Chart(counties).mark_geoshape(
    clip=True,
    stroke='white',
    strokeWidth=0.25,
).encode(
    color=alt.Color(
        'unemployment_percentile:Q',
        title='Unemployment percentile (US counties)',
        scale=alt.Scale(domain=[0, 100], scheme='oranges'),
        legend=None,
    ),
    opacity=alt.condition(
        click,
        alt.value(1),
        alt.value(0.12),
    ),
    tooltip=[
        alt.Tooltip('county_name:N', title='County'),
        alt.Tooltip('unemployment_rate:Q', title='Unemployment rate (%)', format='.1f'),
        alt.Tooltip(
            'unemployment_percentile:Q',
            title='US county percentile',
            format='.0f',
        ),
    ],
).transform_lookup(
    lookup='id',
    from_=alt.LookupData(
        county_unemployment,
        'county_id',
        [
            'state_id',
            'county_name',
            'unemployment_rate',
            'unemployment_percentile',
        ],
    ),
).transform_filter(
    "map_metric === 'County unemployment rate'"
)

county_count_layer = alt.Chart(counties, name='county_data_center_counts').mark_geoshape(
    clip=True,
    stroke='white',
    strokeWidth=0.25,
).encode(
    color=alt.Color(
        'data_center_count:Q',
        title='Data centers (Compute Atlas)',
        scale=alt.Scale(domain=[0, county_max_count], scheme='blues'),
        legend=None,
    ),
    opacity=alt.condition(
        click,
        alt.value(1),
        alt.value(0.12),
    ),
    tooltip=[
        alt.Tooltip('county_name:N', title='County'),
        alt.Tooltip('state_name:N', title='State'),
        alt.Tooltip('data_center_count:Q', title='Compute Atlas data centers', format=','),
    ],
).transform_lookup(
    lookup='id',
    from_=alt.LookupData(
        county_map_data,
        'county_id',
        ['county_id', 'state_id', 'county_name', 'data_center_count'],
    ),
).transform_filter(
    "map_metric === 'Data center count' && map_granularity === 'county'"
)

detail_state_layer = alt.Chart(states).mark_geoshape(
    stroke='white',
    strokeWidth=0.8,
).encode(
    color=alt.Color(
        'metric_value:Q',
        title='Selected metric (land price in $/acre)',
        scale=alt.Scale(scheme=metric_color_scheme),
        legend=None,
    ),
    tooltip=[
        alt.Tooltip('state_name:N', title='State'),
        alt.Tooltip('data_center_count:Q', title='Data centers', format=','),
        alt.Tooltip(
            'land_price:Q',
            title=f'Agricultural land value ($/acre, {latest_land_price_year})',
            format='$,.0f',
        ),
        alt.Tooltip('land_price_note:N', title='Land value data'),
        alt.Tooltip(
            'electricity_price:Q',
            title=f'Commercial electricity price (cents/kWh, {latest_electricity_year})',
            format='.2f',
        ),
        alt.Tooltip(
            'population:Q',
            title=f'Population estimate ({population_year})',
            format=',',
        ),
    ],
).transform_lookup(
    lookup='id',
    from_=alt.LookupData(
        df,
        'state_id',
        [
            'state_id',
            'state_name',
            'data_center_count',
            'land_price',
            'land_price_is_estimate',
            'land_price_note',
            'electricity_price',
            'population',
        ],
    ),
).transform_filter(
    {'param': 'selected_state', 'empty': False},
).transform_calculate(
    metric_value=metric_value_expression,
)

water_mode = alt.param(name='water_mode', value=False)
water_status = alt.param(name='water_status', value='all')
point_layer = alt.Chart(overview_points_df, name='overview_facilities').mark_point(
    clip=True,
    filled=True,
    size=36,
    opacity=0.8,
    stroke='white',
    strokeWidth=0.5,
).encode(
    longitude='longitude:Q',
    latitude='latitude:Q',
    color=alt.Color(
        'status:N',
        legend=None,
        scale=alt.Scale(
            domain=status_domain,
            range=['#238b45', '#ff7f0e', '#9467bd', '#1f77b4', '#7f7f7f'],
        ),
        sort=status_domain,
    ),
    shape=alt.Shape(
        'facility_type:N',
        title='Facility type',
        scale=alt.Scale(
            domain=['data_center', 'power_generation', 'crypto_mining'],
            range=['circle', 'square', 'triangle-up'],
        ),
    ),
    tooltip=[
        alt.Tooltip('name:N', title='Facility'),
        alt.Tooltip('facility_type:N', title='Facility type'),
        alt.Tooltip('company:N', title='Company'),
        alt.Tooltip('city:N', title='City'),
        alt.Tooltip('county:N', title='County'),
        alt.Tooltip('state:N', title='State'),
        alt.Tooltip('status:N', title='Status'),
        alt.Tooltip('confidence:N', title='Data confidence'),
        alt.Tooltip('capacity_operational_mw:Q', title='Operational capacity (MW)'),
        alt.Tooltip('capacity_planned_mw:Q', title='Planned capacity (MW)'),
        alt.Tooltip('source_count:Q', title='Sources'),
        alt.Tooltip('primary_source_url:N', title='Primary source'),
        alt.Tooltip('detail_url:N', title='Facility details'),
    ],
).transform_filter(
    '(water_mode ? (water_status === "all" ? indexof(["operational", "under_construction", "permitted", "proposed"], datum.status) >= 0 : datum.status === water_status) : show_points) && '
    '(length(facility_types) === 0 || indexof(facility_types, datum.facility_type) >= 0) && '
    '(length(facility_statuses) === 0 || indexof(facility_statuses, datum.status) >= 0)'
).transform_filter(
    selected_state_predicate
)

detail_point_layer = alt.Chart(overview_points_df).mark_point(
    filled=True,
    size=48,
    opacity=0.85,
    stroke='white',
    strokeWidth=0.7,
).encode(
    longitude='longitude:Q',
    latitude='latitude:Q',
    color=alt.Color(
        'status:N',
        legend=None,
        scale=alt.Scale(
            domain=status_domain,
            range=['#238b45', '#ff7f0e', '#9467bd', '#1f77b4', '#7f7f7f'],
        ),
        sort=status_domain,
    ),
    shape=alt.Shape(
        'facility_type:N',
        legend=None,
        scale=alt.Scale(
            domain=['data_center', 'power_generation', 'crypto_mining'],
            range=['circle', 'square', 'triangle-up'],
        ),
    ),
    tooltip=[
        alt.Tooltip('name:N', title='Facility'),
        alt.Tooltip('facility_type:N', title='Facility type'),
        alt.Tooltip('company:N', title='Operator'),
        alt.Tooltip('city:N', title='City'),
        alt.Tooltip('county:N', title='County'),
        alt.Tooltip('state:N', title='State'),
        alt.Tooltip('status:N', title='Status'),
        alt.Tooltip('confidence:N', title='Data confidence'),
        alt.Tooltip('capacity_operational_mw:Q', title='Operational capacity (MW)'),
        alt.Tooltip('capacity_planned_mw:Q', title='Planned capacity (MW)'),
        alt.Tooltip('source_count:Q', title='Sources'),
        alt.Tooltip('primary_source_url:N', title='Primary source'),
        alt.Tooltip('detail_url:N', title='Facility details'),
    ],
).transform_filter(
    '(water_mode ? (water_status === "all" ? indexof(["operational", "under_construction", "permitted", "proposed"], datum.status) >= 0 : datum.status === water_status) : show_points) && '
    '(length(facility_types) === 0 || indexof(facility_types, datum.facility_type) >= 0) && '
    '(length(facility_statuses) === 0 || indexof(facility_statuses, datum.status) >= 0)'
).transform_filter(
    {'param': 'selected_state', 'empty': False},
)

map_chart = alt.layer(state_layer, county_layer, county_count_layer, point_layer).project(
    type='albersUsa',
    scale=alt.ExprRef(expr='990 * overview_zoom'),
    translate=alt.ExprRef(expr='[420 + 29 * overview_zoom + overview_pan_x, 230 - 3 * overview_zoom + overview_pan_y]'),
).properties(
    name='overview_map',
    width=840,
    height=460,
    title='US Overview (click to select; Ctrl+click to compare)',
)

detail_map = alt.layer(detail_state_layer, detail_point_layer).project(
    type='mercator',
).properties(
    width=575,
    height=420,
    title='Selected State(s) Detail',
)

parallel_dimensions = [
    ('Data centers', 'data_center_count'),
    ('Land price ($/acre)', 'land_price'),
    ('Electricity (cents/kWh)', 'electricity_price'),
    ('Population', 'population'),
    ('Unemployment rate (%)', 'unemployment_rate'),
    ('Water stress (WRI score 0-5)', 'water_stress'),
]
parallel_records = []
parallel_axis_records = []
parallel_tick_records = []

for dimension_index, (dimension, field) in enumerate(parallel_dimensions):
    parallel_axis_records.append({
        'axis_x': dimension_index,
        'dimension': dimension,
    })

    minimum = float(df[field].min())
    maximum = float(df[field].max())
    if pd.isna(minimum) or pd.isna(maximum):
        raise ValueError(f'Missing values found for parallel-coordinate dimension {dimension}')
    value_range = maximum - minimum
    for _, row in df.iterrows():
        missing = pd.isna(row[field])
        value = float(row[field]) if not missing else None
        if missing:
            normalized_value = None
        elif value_range:
            normalized_value = 0.02 + 0.96 * (value - minimum) / value_range
        else:
            normalized_value = 0.5
        parallel_records.append({
            'state_id': int(row['state_id']),
            'state_name': row['state_name'],
            'axis_x': dimension_index,
            'normalized_value': normalized_value,
            'data_center_count': int(row['data_center_count']),
            'land_price': float(row['land_price']),
            'land_price_note': row['land_price_note'],
            'electricity_price': float(row['electricity_price']),
            'population': int(row['population']),
            'unemployment_rate': float(row['unemployment_rate']),
            'water_stress': float(row['water_stress']) if not pd.isna(row['water_stress']) else None,
        })
        for tick_fraction in (0, 0.5, 1):
            tick_value = minimum + value_range * tick_fraction
            if field == 'land_price':
                tick_label = f'${tick_value / 1000:,.0f}k'
            elif field == 'electricity_price':
                tick_label = f'{tick_value:.1f}'
            elif field == 'unemployment_rate':
                tick_label = f'{tick_value:.1f}%'
            elif field == 'water_stress':
                tick_label = f'{tick_value:.1f}'
            else:
                tick_label = f'{tick_value:,.0f}'
            parallel_tick_records.append({
                'axis_x': dimension_index,
                'tick_x_start': dimension_index - 0.035,
                'tick_x_end': dimension_index + 0.035,
                'normalized_value': 0.02 + 0.96 * tick_fraction,
                'tick_label': tick_label,
            })

parallel_data = pd.DataFrame(parallel_records)
parallel_axes = pd.DataFrame(parallel_axis_records)
parallel_ticks = pd.DataFrame(parallel_tick_records)
parallel_x_scale = alt.Scale(domain=[-0.6, 5.6], nice=False)
parallel_y_scale = alt.Scale(domain=[-0.04, 1.1], nice=False)

parallel_lines = alt.Chart(parallel_data).mark_line(
    cursor='pointer',
    opacity=0.28,
).encode(
    x=alt.X('axis_x:Q', scale=parallel_x_scale, axis=None),
    y=alt.Y('normalized_value:Q', scale=parallel_y_scale, axis=None),
    detail='state_name:N',
    order=alt.Order('axis_x:Q'),
    color=alt.value('#4b8b78'),
    size=alt.condition(
        selected_state_predicate,
        alt.value(2.5),
        alt.value(0.65),
        empty=False,
    ),
    opacity=alt.condition(
        selected_state_predicate,
        alt.value(0.9),
        alt.value(0.24),
        empty=False,
    ),
    tooltip=[
        alt.Tooltip('state_id:Q', title='State ID'),
        alt.Tooltip('state_name:N', title='State'),
        alt.Tooltip('data_center_count:Q', title='Data centers', format=','),
        alt.Tooltip('land_price:Q', title='Land value ($/acre)', format='$,.0f'),
        alt.Tooltip('land_price_note:N', title='Land value source'),
        alt.Tooltip('electricity_price:Q', title='Commercial electricity (cents/kWh)', format='.2f'),
        alt.Tooltip('population:Q', title=f'Population ({population_year})', format=','),
        alt.Tooltip(
            'unemployment_rate:Q',
            title='Weighted unemployment rate (2025, %)',
            format='.2f',
        ),
        alt.Tooltip(
            'water_stress:Q',
            title='Average annual water stress (WRI, 0-5)',
            format='.2f',
        ),
    ],
).transform_filter(
    selected_state_predicate
)
parallel_axis_lines = alt.Chart(parallel_axes).mark_rule(
    color='#9ba7a3',
    strokeWidth=1,
).encode(
    x=alt.X('axis_x:Q', scale=parallel_x_scale, axis=None),
    y=alt.Y('axis_start:Q', scale=parallel_y_scale, axis=None),
    y2='axis_end:Q',
).transform_calculate(
    axis_start='0.02',
    axis_end='0.98',
)
parallel_tick_marks = alt.Chart(parallel_ticks).mark_rule(
    color='#9ba7a3',
    strokeWidth=1,
).encode(
    x=alt.X('tick_x_start:Q', scale=parallel_x_scale, axis=None),
    x2='tick_x_end:Q',
    y=alt.Y('normalized_value:Q', scale=parallel_y_scale, axis=None),
)
parallel_tick_labels = alt.Chart(parallel_ticks).mark_text(
    align='left',
    baseline='middle',
    dx=6,
    fontSize=9,
    color='#626d69',
).encode(
    x=alt.X('axis_x:Q', scale=parallel_x_scale, axis=None),
    y=alt.Y('normalized_value:Q', scale=parallel_y_scale, axis=None),
    text='tick_label:N',
)
parallel_dimension_labels = alt.Chart(parallel_axes).mark_text(
    align='center',
    baseline='bottom',
    fontSize=11,
    fontWeight='bold',
    color='#333333',
).encode(
    x=alt.X('axis_x:Q', scale=parallel_x_scale, axis=None),
    y=alt.Y(datum=1.04, scale=parallel_y_scale, axis=None),
    text='dimension:N',
)
parallel_chart = alt.layer(
    parallel_lines,
    parallel_axis_lines,
    parallel_tick_marks,
    parallel_tick_labels,
    parallel_dimension_labels,
).properties(
    width=1150,
    height=500,
    title=alt.TitleParams(
        text='Data Centers by State',
        subtitle=(
            f'Numeric axes are scaled independently. '
            f'Latest data: land {latest_land_price_year}, electricity {latest_electricity_year}, '
            f'population {population_year}, unemployment 2025; water stress is average WRI facility score. '
            f'Click up to 4 states to compare.'
        ),
    ),
)

state_comparison_colors = ['#0072B2', '#D55E00', '#009E73', '#CC79A7']
profile_bars = alt.Chart(profile_df).mark_bar(
    cornerRadiusEnd=3,
).encode(
    x=alt.X(
        'category:N',
        title=None,
        sort=[metric[0] for metric in profile_metrics],
        axis=alt.Axis(labelAngle=0, labelLimit=100),
    ),
    xOffset=alt.XOffset('state_name:N'),
    y=alt.Y(
        'percentile_rank:Q',
        title='Percentile among states',
        scale=alt.Scale(domain=[0, 100]),
        axis=alt.Axis(orient='left'),
    ),
    color=alt.Color(
        'comparison_slot:O',
        legend=None,
        scale=alt.Scale(
            domain=[0, 1, 2, 3],
            range=state_comparison_colors,
        ),
    ),
    tooltip=[
        alt.Tooltip('state_name:N', title='State'),
        alt.Tooltip('category:N', title='Attribute'),
        alt.Tooltip('value_label:N', title='Value'),
        alt.Tooltip('percentile_rank:Q', title='Percentile among states', format='.1f'),
        alt.Tooltip('value_note:N', title='Data note'),
    ],
).transform_filter(
    {'param': 'selected_state', 'empty': False},
).transform_calculate(
    comparison_slot='indexof(selected_state.state_id || [], datum.state_id)',
)

profile_total = alt.Chart(profile_df).transform_filter(
    {'param': 'selected_state', 'empty': False},
).transform_filter(
    'isValid(datum.percentile_rank)',
).transform_aggregate(
    total_percentile='sum(percentile_rank)',
    states_with_data='valid(percentile_rank)',
    groupby=['category', 'category_order'],
).mark_line(
    color='#344955',
    strokeWidth=2.5,
    point=alt.OverlayMarkDef(filled=True, color='#344955', size=48),
).encode(
    x=alt.X(
        'category:N',
        sort=[metric[0] for metric in profile_metrics],
    ),
    y=alt.Y(
        'total_percentile:Q',
        title='Combined percentile',
        axis=alt.Axis(orient='right'),
    ),
    tooltip=[
        alt.Tooltip('category:N', title='Attribute'),
        alt.Tooltip('total_percentile:Q', title='Combined percentile', format='.1f'),
        alt.Tooltip('states_with_data:Q', title='States with data', format='.0f'),
    ],
)

profile_chart = alt.layer(
    profile_bars,
    profile_total,
).resolve_scale(
    y='independent',
).properties(
    width=575,
    height=420,
    title=alt.TitleParams(
        text='Selected State Comparison',
        subtitle='Bars show each state’s percentile; the line shows their combined percentile. Hover for original values.',
    ),
)

ranking_value = (
    "map_metric === 'County unemployment rate' ? datum.unemployment_rate : "
    f"({metric_value_expression})"
)
ranking_chart = alt.Chart(df, name='state_ranking').transform_calculate(
    ranked_value=ranking_value,
    rank_label="format(datum.ranked_value, map_metric === 'Land price' ? '$,.0f' : "
               "map_metric === 'Commercial electricity price' || map_metric === "
               "'County unemployment rate' || map_metric === 'Water stress' ? ',.1f' : ',.0f') + "
               "(map_metric === 'County unemployment rate' ? '%' : '')",
).transform_filter(
    'isValid(datum.ranked_value)'
).transform_window(
    row='row_number()',
    sort=[alt.SortField('ranked_value', order='descending'), alt.SortField('state_name')],
).transform_filter(
    'datum.row <= 10'
).mark_bar(cursor='pointer', cornerRadiusEnd=2).encode(
    x=alt.X('ranked_value:Q', title=None, axis=None),
    y=alt.Y('state_name:N', sort=alt.EncodingSortField(field='row'), title=None,
            axis=alt.Axis(labelLimit=135, ticks=False, domain=False)),
    color=alt.condition(selected_state_predicate, alt.value('#284e63'), alt.value('#82a9bd'), empty=False),
    tooltip=[alt.Tooltip('state_name:N', title='State'), alt.Tooltip('rank_label:N', title='Value')],
).properties(
    width=175,
    height=460,
    title=alt.TitleParams('Top 10 states', subtitle='Ranked by selected map metric'),
)

# Reserve space inside the shared Vega layout for the HTML comparison panel.
water_space = alt.Chart(alt.Data(values=[{}]), name='water_space').mark_point(
    opacity=0
).properties(width=1150, height=0, view=alt.ViewConfig(stroke=None))

overview = alt.hconcat(ranking_chart, map_chart, spacing=8).resolve_scale(color='independent')
dashboard = alt.vconcat(
    overview, water_space, spacing=8
).add_params(
    show_points,
    facility_types,
    facility_statuses,
    map_metric,
    map_granularity,
    water_mode,
    water_status,
    map_zoom,
    map_pan_x,
    map_pan_y,
).configure_view(
    stroke='#d9dfdc',
    strokeWidth=1,
    cornerRadius=5,
)
dashboard.config.style = {'view': {'stroke': '#d9dfdc', 'strokeWidth': 1, 'cornerRadius': 5}}
dashboard_path = Path(__file__).resolve().parent / 'data_center_dashboard_1.html'
dashboard.save(dashboard_path, embed_options={"actions": False})
dashboard_html = dashboard_path.read_text(encoding='utf-8')
spec_start_marker = 'var spec = '
spec_start = dashboard_html.index(spec_start_marker) + len(spec_start_marker)
spec_end = dashboard_html.index(';\n', spec_start)
dashboard_spec = json.loads(dashboard_html[spec_start:spec_end])
selected_state_param = next(
    (param for param in dashboard_spec.get('params', []) if param.get('name') == 'selected_state'),
    None,
)
if selected_state_param is None:
    raise ValueError('Could not find the selected_state selection in the generated chart')
state_shape_view = next(
    (
        view for view in selected_state_param.get('views', [])
        if view.startswith('overview_state_shapes')
    ),
    None,
)
if state_shape_view is None:
    raise ValueError('Could not identify the state-shape view for the selected_state selection')
selected_state_param['views'] = [state_shape_view]
dashboard_html = (
    dashboard_html[:spec_start]
    + json.dumps(dashboard_spec)
    + dashboard_html[spec_end:]
)
legend_metrics = {
    'Data center count': {
        'title': 'Data centers',
        'scheme': 'blues',
        'min': float(df['data_center_count'].min()),
        'max': float(df['data_center_count'].max()),
        'county_max': county_max_count,
        'format': 'count',
    },
    'Land price': {
        'title': f'Land value ($/acre, {latest_land_price_year})',
        'scheme': 'greens',
        'min': float(df['land_price'].min()),
        'max': float(df['land_price'].max()),
        'format': 'currency',
    },
    'Commercial electricity price': {
        'title': f'Commercial electricity (cents/kWh, {latest_electricity_year})',
        'scheme': 'oranges',
        'min': float(df['electricity_price'].min()),
        'max': float(df['electricity_price'].max()),
        'format': 'decimal',
    },
    'Population': {
        'title': f'Population ({population_year})',
        'scheme': 'purples',
        'min': float(df['population'].min()),
        'max': float(df['population'].max()),
        'format': 'count',
    },
    'Water stress': {
        'title': 'Average water stress (WRI score, 0-5)',
        'scheme': 'purples',
        'min': float(df['water_stress'].min()),
        'max': float(df['water_stress'].max()),
        'format': 'decimal',
    },
    'County unemployment rate': {
        'title': 'Unemployment percentile (US counties)',
        'scheme': 'oranges',
        'min': 0,
        'max': 100,
        'format': 'percentile',
    },
}
legend_metrics_json = json.dumps(legend_metrics)
state_options_json = df[['state_id', 'state_name']].to_json(orient='records')
state_ids_json = json.dumps({
    abbreviation: state_id
    for abbreviation, (_, state_id) in STATE_INFO.items()
})
dashboard_styles = """
    html { overflow: hidden; }
    body { margin: 0; overflow: hidden; }
    #dashboard-toolbar {
      position: fixed;
      top: 0;
      left: 0;
      z-index: 10;
      width: 190px;
      height: 100vh;
      box-sizing: border-box;
      padding: 10px 16px;
      background: #fff;
      border-right: 1px solid #d9dfdc;
      overflow-y: auto;
      font: 14px/1.35 Arial, sans-serif;
    }
    #metric-menu {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 6px;
    }
    #metric-menu h2 { margin: 0 6px 0 0; font-size: 14px; }
    #metric-menu button {
      padding: 8px 10px;
      border: 0;
      border-radius: 5px;
      background: #f4f6f5;
      color: #333;
      font: inherit;
      cursor: pointer;
    }
    #metric-menu button:hover { background: #eef3f1; }
    #metric-menu button[aria-pressed="true"] {
      background: #e1eee9;
      color: #176b55;
      font-weight: 700;
    }
    #map-granularity { display: inline-flex; gap: 2px; padding: 2px; border-radius: 6px; background: #e8edeb; }
    #map-granularity button { padding: 6px 9px; }
    #map-granularity[hidden] { display: none; }
    #toolbar-options {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 6px 20px;
      margin-top: 8px;
    }
    .facility-filter { margin: 0; padding: 4px 8px 6px; border: 1px solid #d9dfdc; border-radius: 5px; }
    .facility-filter legend { padding: 0 4px; font-weight: 700; }
    #state-picker, #selected-states { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px; }
    #zoom-reset, #state-picker input, #state-picker button, #selected-states button {
      font: inherit; padding: 4px 8px; border: 1px solid #d9dfdc; border-radius: 5px;
    }
    #state-picker input { width: 10rem; max-width: 100%; }
    #zoom-reset, #state-picker button, #selected-states button { cursor: pointer; background: #eef3f1; color: #245448; }
    .facility-filter-options { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; }
    .facility-filter-options label { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
    #map-legend {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 4px 8px;
      font-size: 12px;
    }
    #map-legend-title { font-weight: 700; }
    #map-legend-content, #map-legend-labels { display: flex; align-items: center; gap: 6px; }
    #map-legend-scale { width: 88px; height: 10px; border-radius: 3px; }
    #chart-frame {
      position: fixed;
      left: 190px;
      top: 0;
      right: 0;
      bottom: 0;
      margin: 0;
      box-sizing: border-box;
      height: 100vh;
      padding: 8px;
      overflow: hidden;
    }
    #overview-controls:not([hidden]) {
      position: absolute;
      z-index: 1;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 6px;
      background: #fff;
      border: 1px solid #d9dfdc;
      border-radius: 5px;
    }
    #zoom-reset { font-size: 12px; white-space: nowrap; }
    #water-panel {
      position: absolute; z-index: 1; box-sizing: border-box;
      padding: 16px 20px; border: 1px solid #d9dfdc; border-radius: 5px;
      background: #fff; color: #243746; font: 14px/1.45 Arial, sans-serif;
    }
    #water-heading { margin: 0; font-size: 18px; }
    #water-panel p { margin: 6px 0; }
    #water-panel select, #water-sites button { font: inherit; }
    #water-panel a { color: #245448; }
    #water-sites { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    #water-sites:empty { display: none; }
    #water-sites button {
      padding: 4px 8px; background: #f6f8f8; color: inherit; cursor: pointer;
      border: 1px solid #d9dfdc; border-radius: 5px;
    }
    #water-results { margin-top: 10px; }
    #water-toggle[aria-expanded="true"] { background: #e1eee9; color: #176b55; }
    #zoom-reset:disabled { opacity: 0.65; cursor: default; }
    #chart-frame #vis { position: relative; display: block; width: max-content; margin-inline: auto; }
    #vis > .chart-wrapper { display: block; }
    #vis .vega-actions, #vis details { display: none; }
"""
dashboard_toolbar = """  <header id="dashboard-toolbar">
    <nav id="metric-menu" aria-label="Map metric">
      <h2>Map metric</h2>
      <button type="button" data-metric="Data center count" aria-pressed="true">Data center count</button>
      <button type="button" data-metric="Land price" aria-pressed="false">Land price</button>
      <button type="button" data-metric="Commercial electricity price" aria-pressed="false">Commercial electricity price</button>
      <button type="button" data-metric="Population" aria-pressed="false">Population</button>
      <button type="button" data-metric="Water stress" aria-pressed="false">Water stress</button>
      <button type="button" data-metric="County unemployment rate" aria-pressed="false">County unemployment rate</button>
      <button id="water-toggle" type="button" aria-controls="water-panel" aria-expanded="false">Seasonal facility chart</button>
      <div id="map-granularity" role="group" aria-label="Data center count map division" hidden>
        <button type="button" data-granularity="state" aria-pressed="true">By state</button>
        <button type="button" data-granularity="county" aria-pressed="false">By county</button>
      </div>
    </nav>
    <div id="toolbar-options">
      <label><input id="show-points" type="checkbox"> Show Compute Atlas facility locations</label>
      <fieldset id="facility-type-controls" class="facility-filter" hidden>
        <legend>Facility type</legend>
        <div id="facility-type-filter" class="facility-filter-options" role="group" aria-label="Facility type"></div>
      </fieldset>
      <fieldset id="facility-status-controls" class="facility-filter" hidden>
        <legend>Status</legend>
        <div id="facility-status-filter" class="facility-filter-options" role="group" aria-label="Status"></div>
      </fieldset>
      <form id="state-picker">
        <label for="state-search">Add state</label>
        <input id="state-search" list="state-options" placeholder="Search states" autocomplete="off" required>
        <datalist id="state-options"></datalist>
        <button type="submit">Add</button>
      </form>
      <span id="selected-states" aria-label="Selected states"></span>
      <span id="selection-message" role="status"></span>
      <span id="county-view-note" role="status" hidden></span>
    </div>
  </header>
  <main id="chart-frame">
    <section id="water-panel" hidden aria-labelledby="water-heading">
      <h2 id="water-heading">Seasonal water stress</h2>
      <p>Click facility dots on the overview map to compare up to three sites. Click again to remove a site.</p>
      <label>Facility status <select id="water-status">
        <option value="all">All active and planned</option>
        <option value="operational">Operational</option>
        <option value="under_construction">Under construction</option>
        <option value="permitted">Permitted</option>
        <option value="proposed">Proposed</option>
      </select></label>
      <p id="water-message" role="status"></p>
      <div id="water-sites" aria-label="Selected facilities"></div>
      <div id="water-results" hidden></div>
      <p>Modeled water stress in each facility’s surrounding basin. Gaps indicate missing scores.
        <a href="https://www.wri.org/data/aqueduct-global-maps-40-data">WRI Aqueduct 4.0</a></p>
    </section>
    <div id="vis"></div>
    <div id="overview-controls" hidden>
      <aside id="map-legend" aria-live="polite">
        <span id="map-legend-title"></span>
        <div id="map-legend-content">
          <div id="map-legend-labels">
            <span id="map-legend-min"></span>
            <div id="map-legend-scale" aria-hidden="true"></div>
            <span id="map-legend-max"></span>
          </div>
        </div>
      </aside>
      <button id="zoom-reset" type="button" disabled>Reset map</button>
    </div>
  </main>"""
dashboard_html = dashboard_html.replace(
    '  <meta charset="UTF-8">\n',
    '  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n',
    1,
).replace(
    '  <style>\n',
    '  <style>\n' + dashboard_styles.lstrip('\n'),
    1,
).replace(
    '  <div id="vis"></div>',
    dashboard_toolbar,
    1,
)
embed_script = (
    '      vegaEmbed("#vis", spec, embedOpt)\n'
    '        .catch(error => showError(el, error));'
)
interactive_embed_script = (
    '      vegaEmbed("#vis", spec, embedOpt)\n'
    '        .then(({view}) => {\n'
    '          const frame = document.getElementById("chart-frame");\n'
    '          const chart = el.querySelector("canvas.marks, svg.marks");\n'
    '          const fitChart = () => {\n'
    '            if (chart.offsetWidth > 0) {\n'
    '              el.style.zoom = Math.min(1, frame.clientWidth / el.offsetWidth);\n'
    '            }\n'
    '          };\n'
    '          const resizeObserver = new ResizeObserver(fitChart);\n'
    '          resizeObserver.observe(frame);\n'
    '          resizeObserver.observe(chart);\n'
    '          fitChart();\n'
    '\n'
    '          const points = document.getElementById("show-points");\n'
    '          points.checked = view.signal("show_points");\n'
    '          const facilityTypeControls = document.getElementById("facility-type-controls");\n'
    '          const facilityStatusControls = document.getElementById("facility-status-controls");\n'
    '          const updateFacilityFilterVisibility = () => {\n'
    '            facilityTypeControls.hidden = !points.checked;\n'
    '            facilityStatusControls.hidden = !points.checked;\n'
    '          };\n'
    '          updateFacilityFilterVisibility();\n'
    '          points.addEventListener("change", () => {\n'
    '            updateFacilityFilterVisibility();\n'
    '            view.signal("show_points", points.checked).runAsync().catch(error => showError(el, error));\n'
    '          });\n'
    f'          const facilityTypes = {facility_type_options_json};\n'
    f'          const facilityStatuses = {facility_status_options_json};\n'
    '          const facilityTypeFilter = document.getElementById("facility-type-filter");\n'
    '          const facilityStatusFilter = document.getElementById("facility-status-filter");\n'
    '          const addCheckboxes = (container, options, selectedValues, name) => {\n'
    '            container.replaceChildren(...options.map(({label, value}) => {\n'
    '              const id = name + "-" + value;\n'
    '              const checkbox = document.createElement("input");\n'
    '              checkbox.type = "checkbox";\n'
    '              checkbox.id = id;\n'
    '              checkbox.value = value;\n'
    '              checkbox.checked = selectedValues.includes(value);\n'
    '              const optionLabel = document.createElement("label");\n'
    '              optionLabel.htmlFor = id;\n'
    '              optionLabel.append(checkbox, document.createTextNode(label));\n'
    '              return optionLabel;\n'
    '            }));\n'
    '          };\n'
    '          addCheckboxes(facilityTypeFilter, facilityTypes, view.signal("facility_types"), "facility-type");\n'
    '          addCheckboxes(facilityStatusFilter, facilityStatuses, view.signal("facility_statuses"), "facility-status");\n'
    '          facilityTypeFilter.addEventListener("change", () => {\n'
    '            const selected = Array.from(facilityTypeFilter.querySelectorAll("input:checked"), input => input.value);\n'
    '            view.signal("facility_types", selected).runAsync().catch(error => showError(el, error));\n'
    '          });\n'
    '          facilityStatusFilter.addEventListener("change", () => {\n'
    '            const selected = Array.from(facilityStatusFilter.querySelectorAll("input:checked"), input => input.value);\n'
    '            view.signal("facility_statuses", selected).runAsync().catch(error => showError(el, error));\n'
    '          });\n'
    '\n'
    f'          const states = {state_options_json};\n'
    '          const stateNames = new Map(states.map(({state_id, state_name}) => [state_id, state_name]));\n'
    f'          const stateColors = {json.dumps(state_comparison_colors)};\n'
    f'          const stateIds = {state_ids_json};\n'
    '          const store = "selected_state_store";\n'
    '          const unit = spec.params.find(param => param.name === "selected_state").views[0];\n'
    '          const chips = document.getElementById("selected-states");\n'
    '          const search = document.getElementById("state-search");\n'
    '          const message = document.getElementById("selection-message");\n'
    '          const options = document.getElementById("state-options");\n'
    '          const currentIds = () => view.data(store).map(row => row.values[0]);\n'
    '          let selectionQueue = Promise.resolve();\n'
    '          function editSelection(edit) {\n'
    '            selectionQueue = selectionQueue.then(async () => {\n'
    '              const before = currentIds();\n'
    '              const after = edit(before);\n'
    '              if (after.length > 4) {\n'
    '                message.textContent = "Remove a state before adding another (maximum four).";\n'
    '                return;\n'
    '              }\n'
    '              message.textContent = "";\n'
    '              if (before.length === after.length && before.every((id, i) => id === after[i])) return;\n'
    '              const rows = after.map(id => ({\n'
    '                unit,\n'
    '                fields: [{field: "state_id", type: "E"}],\n'
    '                values: [id],\n'
    '              }));\n'
    '              await view.change(store, vega.changeset().remove(() => true).insert(rows)).runAsync();\n'
    '            }).catch(error => showError(el, error));\n'
    '          }\n'
    '          function renderChips(ids) {\n'
    '            chips.replaceChildren(...ids.filter(id => stateNames.has(id)).map((id, index) => {\n'
    '              const name = stateNames.get(id);\n'
    '              const chip = document.createElement("button");\n'
    '              chip.type = "button";\n'
    '              chip.textContent = name + " ×";\n'
    '              chip.style.borderLeft = "4px solid " + stateColors[index];\n'
    '              chip.setAttribute("aria-label", "Remove " + name);\n'
    '              chip.onclick = () => {\n'
    '                editSelection(previous => previous.filter(value => value !== id));\n'
    '                search.focus();\n'
    '              };\n'
    '              return chip;\n'
    '            }));\n'
    '          }\n'
    '          options.replaceChildren(...states.map(({state_name}) => {\n'
    '            const option = document.createElement("option");\n'
    '            option.value = state_name;\n'
    '            return option;\n'
    '          }));\n'
    '          document.getElementById("state-picker").addEventListener("submit", event => {\n'
    '            event.preventDefault();\n'
    '            const state = states.find(row => row.state_name.toLowerCase() === search.value.trim().toLowerCase());\n'
    '            if (!state) {\n'
    '              message.textContent = "Choose a state from the list.";\n'
    '              return;\n'
    '            }\n'
    '            editSelection(ids => ids.includes(state.state_id) ? ids : [...ids, state.state_id]);\n'
    '            search.value = "";\n'
    '          });\n'
    '          view.addSignalListener("selected_state", (_, selection) => {\n'
    '            message.textContent = "";\n'
    '            renderChips(selection.state_id || []);\n'
    '          });\n'
    '          renderChips(currentIds());\n'
    '          const overviewItem = item => item?.mark?.name === "overview_map_group" ||\n'
    '            item?.mark?.group?.mark?.name === "overview_map_group";\n' 
    '          const findGroup = (node, name) => {\n'
    '            if (node.mark?.name === name) return node;\n'
    '            for (const child of node.items || []) {\n'
    '              const group = findGroup(child, name);\n'
    '              if (group) return group;\n'
    '            }\n'
    '          };\n'
    '          const overview = findGroup(view.scenegraph().root, "overview_map_group");\n'
    '          const controls = document.getElementById("overview-controls");\n'
    '          const reset = document.getElementById("zoom-reset");\n'
    '          el.append(controls);\n'
    '          controls.hidden = false;\n'
    '\n'
    '          function groupOrigin(item) {\n'
    '            const [x, y] = view.origin();\n'
    '            let left = x, top = y;\n'
    '            for (let group = item; group; group = group.mark.group) {\n'
    '              left += group.x || 0;\n'
    '              top += group.y || 0;\n'
    '            }\n'
    '            return [left, top];\n'
    '          }\n'
    '\n'
    '          function placeControls() {\n'
    '            const [left, top] = groupOrigin(overview);\n'
    '            const chartRect = chart.getBoundingClientRect();\n'
    '            const visRect = el.getBoundingClientRect();\n'
    '            const scale = parseFloat(el.style.zoom) || 1;\n'
    '            controls.style.left = ((chartRect.left - visRect.left) / scale + left + overview.width - controls.offsetWidth - 8) + "px";\n'
    '            controls.style.top = ((chartRect.top - visRect.top) / scale + top + 8) + "px";\n'
    '          }\n'
    '          resizeObserver.observe(controls);\n'
    '          view.addResizeListener(placeControls);\n'
    '          placeControls();\n'
    '\n'
    '          function mapPosition(event) {\n'
    '            const rect = chart.getBoundingClientRect();\n'
    '            const scale = parseFloat(el.style.zoom) || 1;\n'
    '            const [left, top] = groupOrigin(overview);\n'
    '            return [(event.clientX - rect.left) / scale - left,\n'
    '              (event.clientY - rect.top) / scale - top];\n'
    '          }\n'
    '          const insideMap = (x, y) => x >= 0 && x <= overview.width && y >= 0 && y <= overview.height;\n'
    '          let drag = null;\n'
    '          let dragged = false;\n'
    '          const updateMap = (zoom, x, y) => {\n'
    '            const bound = (value, limit) => Math.max(-limit, Math.min(limit, value));\n'
    '            const panX = bound(x, 100 + 420 * (zoom - 1));\n'
    '            const panY = bound(y, 60 + 230 * (zoom - 1));\n'
    '            view.signal("overview_zoom", zoom)\n'
    '              .signal("overview_pan_x", panX)\n'
    '              .signal("overview_pan_y", panY)\n'
    '              .runAsync().catch(error => showError(el, error));\n'
    '            reset.disabled = zoom === 1 && panX === 0 && panY === 0;\n'
    '          };\n'
    '          reset.onclick = () => updateMap(1, 0, 0);\n'
    '          chart.addEventListener("wheel", event => {\n'
    '            const [x, y] = mapPosition(event);\n'
    '            if (!insideMap(x, y)) return;\n'
    '            event.preventDefault();\n'
    '            const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? overview.height : 1);\n'
    '            const previous = view.signal("overview_zoom");\n'
    '            const zoom = Math.max(1, Math.min(8, previous * Math.exp(-delta * 0.002)));\n'
    '            if (zoom === previous) return;\n'
    '            const ratio = zoom / previous;\n'
    '            const anchorX = x - overview.width / 2;\n'
    '            const anchorY = y - overview.height / 2;\n'
    '            updateMap(zoom,\n'
    '              anchorX + (view.signal("overview_pan_x") - anchorX) * ratio,\n'
    '              anchorY + (view.signal("overview_pan_y") - anchorY) * ratio);\n'
    '          }, {passive: false});\n'
    '          chart.addEventListener("mousedown", event => {\n'
    '            dragged = false;\n'
    '            if (event.button !== 0 || !insideMap(...mapPosition(event))) return;\n'
    '            drag = {\n'
    '              x: event.clientX, y: event.clientY,\n'
    '              panX: view.signal("overview_pan_x"), panY: view.signal("overview_pan_y"),\n'
    '            };\n'
    '          });\n'
    '          window.addEventListener("mousemove", event => {\n'
    '            if (!drag) {\n'
    '              chart.style.cursor = event.target === chart || chart.contains(event.target)\n'
    '                ? (insideMap(...mapPosition(event)) ? "grab" : "") : "";\n'
    '              return;\n'
    '            }\n'
    '            const dx = event.clientX - drag.x;\n'
    '            const dy = event.clientY - drag.y;\n'
    '            if (!dragged && Math.hypot(dx, dy) < 4) return;\n'
    '            dragged = true;\n'
    '            chart.style.cursor = "grabbing";\n'
    '            const scale = parseFloat(el.style.zoom) || 1;\n'
    '            updateMap(view.signal("overview_zoom"), drag.panX + dx / scale, drag.panY + dy / scale);\n'
    '          });\n'
    '          function endDrag() {\n'
    '            drag = null;\n'
    '            chart.style.cursor = "";\n'
    '          }\n'
    '          window.addEventListener("mouseup", endDrag);\n'
    '          window.addEventListener("blur", endDrag);\n'
    f'          const waterProfiles = {water_profiles_json};\n'
    '          const waterToggle = document.getElementById("water-toggle");\n'
    '          const waterPanel = document.getElementById("water-panel");\n'
    '          const waterStatus = document.getElementById("water-status");\n'
    '          const waterMessage = document.getElementById("water-message");\n'
    '          const waterResults = document.getElementById("water-results");\n'
    '          const waterSites = document.getElementById("water-sites");\n'
    '          const waterSpace = findGroup(view.scenegraph().root, "water_space_group");\n'
    '          el.append(waterPanel);\n'
    '          waterPanel.style.width = waterSpace.width + "px";\n'
    '\n'
    '          function placeWater() {\n'
    '            const [left, top] = groupOrigin(waterSpace);\n'
    '            const chartRect = chart.getBoundingClientRect();\n'
    '            const visRect = el.getBoundingClientRect();\n'
    '            const scale = parseFloat(el.style.zoom) || 1;\n'
    '            waterPanel.style.left = ((chartRect.left - visRect.left) / scale + left) + "px";\n'
    '            waterPanel.style.top = ((chartRect.top - visRect.top) / scale + top) + "px";\n'
    '            const height = waterPanel.offsetHeight;\n'
    '            if (view.signal("water_space_height") !== height) {\n'
    '              view.signal("water_space_height", height).runAsync().catch(error => showError(el, error));\n'
    '            }\n'
    '          }\n'
    '          resizeObserver.observe(waterPanel);\n'
    '          view.addResizeListener(placeWater);\n'
    '          const comparedSites = new Map();\n'
    '          const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];\n'
    '          const colors = ["#2166ac", "#a44215", "#23755e"];\n'
    '          const dashPatterns = [[1, 0], [7, 4], [2, 3]];\n'
    '          let waterView;\n'
    '          let waterRenderQueue = Promise.resolve();\n'
    '\n'
    '          function renderWater() {\n'
    '            waterSites.replaceChildren();\n'
    '            const rows = [];\n'
    '            const slots = [...comparedSites.values()].map(site => site.slot);\n'
    '            for (const [id, site] of comparedSites) {\n'
    '              const label = site.name + " (" + site.state + ")";\n'
    '              const remove = document.createElement("button");\n'
    '              remove.type = "button";\n'
    '              remove.textContent = label + " ×";\n'
    '              remove.style.borderLeft = "4px solid " + colors[site.slot];\n'
    '              remove.setAttribute("aria-label", "Remove " + label);\n'
    '              remove.onclick = () => {\n'
    '                comparedSites.delete(id);\n'
    '                waterMessage.textContent = "";\n'
    '                renderWater();\n'
    '              };\n'
    '              waterSites.append(remove);\n'
    '              months.forEach((month, index) => {\n'
    '                const key = "bws_" + String(index + 1).padStart(2, "0") + "_score";\n'
    '                rows.push({month, score: waterProfiles[id]?.[key] ?? null, facility: label, slot: site.slot});\n'
    '              });\n'
    '            }\n'
    '            waterResults.hidden = slots.length === 0;\n'
    '            waterRenderQueue = waterRenderQueue.then(async () => {\n'
    '              if (rows.length) {\n'
    '                if (!waterView) {\n'
    '                  const monthlyChart = {\n'
    '                    width: waterSpace.width - 100, height: 235,\n'
    '                    data: {name: "monthly_scores"},\n'
    '                    mark: {type: "line", point: {filled: true, size: 52}, strokeWidth: 2.5, invalid: "break-paths-show-path-domains"},\n'
    '                    encoding: {\n'
    '                      x: {field: "month", type: "ordinal", sort: months, axis: {title: null, labelAngle: 0, ticks: false}},\n'
    '                      y: {field: "score", type: "quantitative", scale: {domain: [0, 5]}, axis: {title: "Water stress score (0–5)", tickMinStep: 1}},\n'
    '                      color: {field: "slot", type: "nominal", scale: {domain: [0, 1, 2], range: colors}, legend: null},\n'
    '                      strokeDash: {field: "slot", type: "nominal", scale: {domain: [0, 1, 2], range: dashPatterns}, legend: null},\n'
    '                      tooltip: [\n'
    '                        {field: "facility", title: "Facility"},\n'
    '                        {field: "month", title: "Month"},\n'
    '                        {field: "score", type: "quantitative", title: "Water stress score", format: ".2f"}\n'
    '                      ]\n'
    '                    },\n'
    '                    config: {view: {stroke: null}, axis: {gridColor: "#e5ebed", labelColor: "#415461", titleColor: "#243746"}}\n'
    '                  };\n'
    '                  ({view: waterView} = await vegaEmbed(waterResults, monthlyChart, {mode: "vega-lite", renderer: "svg", actions: false}));\n'
    '                }\n'
    '                await waterView.change("monthly_scores", vega.changeset().remove(() => true).insert(rows)).runAsync();\n'
    '              }\n'
    '              placeWater();\n'
    '            }).catch(error => { waterMessage.textContent = "Could not draw the water stress chart."; console.error(error); });\n'
    '          }\n'
    '\n'
    '          waterToggle.onclick = () => {\n'
    '            const enabled = waterPanel.hidden;\n'
    '            waterPanel.hidden = !enabled;\n'
    '            placeWater();\n'
    '            waterToggle.setAttribute("aria-expanded", String(enabled));\n'
    '            view.signal("water_mode", enabled).runAsync().catch(error => showError(el, error));\n'
    '          };\n'
    '          waterStatus.onchange = () => {\n'
    '            view.signal("water_status", waterStatus.value).runAsync().catch(error => showError(el, error));\n'
    '          };\n'
    '          function compareWaterSite(site) {\n'
    '            const id = site.id;\n'
    '            if (comparedSites.has(id)) {\n'
    '              comparedSites.delete(id);\n'
    '            } else if (comparedSites.size >= 3) {\n'
    '              waterMessage.textContent = "Remove a facility before adding another.";\n'
    '              return;\n'
    '            } else {\n'
    '              const usedSlots = new Set([...comparedSites.values()].map(other => other.slot));\n'
    '              comparedSites.set(id, {...site, slot: [0, 1, 2].find(slot => !usedSlots.has(slot))});\n'
    '            }\n'
    '            waterMessage.textContent = waterProfiles[id] ? "" : "No monthly basin scores are available for " + site.name + ".";\n'
    '            renderWater();\n'
    '          }\n'
    '          view.addEventListener("click", (event, item) => {\n'
    '            if (dragged) { dragged = false; return; }\n'
    '            const datum = item?.datum;\n'
    '            const isFacilityPoint = datum?.id != null && typeof datum?.name === "string" &&\n'
    '              typeof datum?.state === "string";\n'
    '            if (!waterPanel.hidden && isFacilityPoint) {\n'
    '              compareWaterSite(datum);\n'
    '              return;\n'
    '            }\n'
    '            const isParallelLine = Number.isInteger(datum?.state_id) && Number.isFinite(datum?.axis_x);\n'
    '            if (!overviewItem(item) && item?.mark?.name !== "state_ranking_marks" && !isParallelLine) return;\n'
    '            const id = datum?.state_id ?? stateIds[datum?.state];\n'
    '            if (!stateNames.has(id)) return;\n'
    '            editSelection(ids => {\n'
    '              if (event.ctrlKey || event.metaKey) {\n'
    '                return ids.includes(id) ? ids.filter(value => value !== id) : [...ids, id];\n'
    '              }\n'
    '              return ids.includes(id) && ids.length === 1 ? ids : [id];\n'
    '            });\n'
    '          });\n'
    f'          const legendMetrics = {legend_metrics_json};\n'
    f'          const countyOmitted = {unmatched_county_facilities};\n'
    '          const schemeColors = {\n'
    '            blues: ["#deebf7", "#9ecae1", "#3182bd"],\n'
    '            greens: ["#e5f5e0", "#a1d99b", "#31a354"],\n'
    '            oranges: ["#fee6ce", "#fdae6b", "#e6550d"],\n'
    '            purples: ["#efedf5", "#bcbddc", "#756bb1"]\n'
    '          };\n'
    '          const formatLegendValue = (value, format) => {\n'
    '            if (format === "currency") return "$" + Math.round(value).toLocaleString();\n'
    '            if (format === "decimal") return value.toFixed(1);\n'
    '            if (format === "percentile") return Math.round(value) + "th";\n'
    '            return Math.round(value).toLocaleString();\n'
    '          };\n'
    '          const granularityGroup = document.getElementById("map-granularity");\n'
    '          const countyViewNote = document.getElementById("county-view-note");\n'
    '          const updateMapControls = metric => {\n'
    '            const countyMode = view.signal("map_granularity") === "county";\n'
    '            granularityGroup.hidden = metric !== "Data center count";\n'
    '            countyViewNote.hidden = metric !== "Data center count" || !countyMode || countyOmitted === 0;\n'
    '            countyViewNote.textContent = countyOmitted + " Atlas facilities without county assignments are omitted.";\n'
    '            granularityGroup.querySelectorAll("[data-granularity]").forEach(button => {\n'
    '              button.setAttribute("aria-pressed", String(button.dataset.granularity === (countyMode ? "county" : "state")));\n'
    '            });\n'
    '          };\n'
    '          const updateLegend = (metric, granularity = view.signal("map_granularity")) => {\n'
    '            const item = legendMetrics[metric];\n'
    '            const max = metric === "Data center count" && granularity === "county" ? item.county_max : item.max;\n'
    '            document.getElementById("map-legend-title").textContent = metric === "Data center count" && granularity === "county" ? "Data centers (Atlas)" : item.title;\n'
    '            document.getElementById("map-legend-scale").style.background =\n'
    '              "linear-gradient(to right, " + schemeColors[item.scheme].join(", ") + ")";\n'
    '            const min = metric === "Data center count" && granularity === "county" ? 0 : item.min;\n'
    '            document.getElementById("map-legend-min").textContent = formatLegendValue(min, item.format);\n'
    '            document.getElementById("map-legend-max").textContent = formatLegendValue(max, item.format);\n'
    '            document.getElementById("map-legend-labels").setAttribute("aria-label",\n'
    '              formatLegendValue(min, item.format) + " to " + formatLegendValue(max, item.format));\n'
    '          };\n'
    '          updateLegend(view.signal("map_metric"));\n'
    '          updateMapControls(view.signal("map_metric"));\n'
    '          granularityGroup.querySelectorAll("[data-granularity]").forEach(button => {\n'
    '            button.addEventListener("click", () => {\n'
    '              view.signal("map_granularity", button.dataset.granularity).runAsync().then(() => {\n'
    '                updateLegend(view.signal("map_metric"), button.dataset.granularity);\n'
    '                updateMapControls(view.signal("map_metric"));\n'
    '              }).catch(error => showError(el, error));\n'
    '            });\n'
    '          });\n'
    '          document.querySelectorAll("#metric-menu [data-metric]").forEach(button => {\n'
    '            button.addEventListener("click", () => {\n'
    '              view.signal("map_metric", button.dataset.metric).runAsync().then(() => {\n'
    '                updateLegend(button.dataset.metric);\n'
    '                updateMapControls(button.dataset.metric);\n'
    '              }).catch(error => showError(el, error));\n'
    '              document.querySelectorAll("#metric-menu [data-metric]").forEach(option => {\n'
    '                option.setAttribute("aria-pressed", String(option === button));\n'
    '              });\n'
    '            });\n'
    '          });\n'
    '        })\n'
    '        .catch(error => showError(el, error));'
)
if embed_script not in dashboard_html:
    raise ValueError('Could not find the Vega embed call to connect the map metric menu')
dashboard_path.write_text(
    dashboard_html.replace(
        embed_script,
        interactive_embed_script,
        1,
    ),
    encoding='utf-8',
)
