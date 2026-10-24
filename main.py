import json
import math
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

radar_categories = ['Data centers', 'Land price', 'Electricity', 'Population', 'Unemployment']
radar_metrics = [
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
]
radar_records = []
for category_order, (category, field, unit, note_field) in enumerate(radar_metrics):
    percentile_ranks = df[field].rank(method='average', pct=True) * 100
    for state_index, row in df.iterrows():
        value = row[field]
        missing = pd.isna(value)
        percentile = float(percentile_ranks.iloc[state_index]) if not missing else None
        angle = -math.pi / 2 + 2 * math.pi * category_order / len(radar_categories)
        radius = (percentile or 0.0) / 100
        if missing:
            value_label = 'No data'
            value_note = 'No source value; shown at the chart center.'
        else:
            if field == 'electricity_price':
                value_label = f'{value:.2f} {unit}'
            elif field == 'unemployment_rate':
                value_label = f'{value:.2f}{unit}'
            else:
                value_label = f'{value:,.0f} {unit}'
            value_note = row[note_field] if note_field else 'Reported value'
        radar_records.append({
            'state_id': int(row['state_id']),
            'state_name': row['state_name'],
            'category': category,
            'category_order': category_order,
            'percentile_rank': percentile,
            'plot_rank': radius * 100,
            'x': radius * math.cos(angle),
            'y': radius * math.sin(angle),
            'value_label': value_label,
            'value_note': value_note,
        })

radar_df = pd.DataFrame(radar_records)
radar_line_df = pd.concat(
    [
        radar_df,
        radar_df.loc[radar_df['category_order'].eq(0)].assign(
            category_order=len(radar_categories)
        ),
    ],
    ignore_index=True,
)
radar_grid_records = []
for ring_rank in (20, 40, 60, 80, 100):
    for category_order in range(len(radar_categories) + 1):
        angle = -math.pi / 2 + 2 * math.pi * category_order / len(radar_categories)
        radius = ring_rank / 100
        radar_grid_records.append({
            'ring_rank': ring_rank,
            'category_order': category_order,
            'x': radius * math.cos(angle),
            'y': radius * math.sin(angle),
        })
radar_grid_df = pd.DataFrame(radar_grid_records)

radar_axis_records = []
radar_label_records = []
for category_order, category in enumerate(radar_categories):
    angle = -math.pi / 2 + 2 * math.pi * category_order / len(radar_categories)
    radar_axis_records.extend([
        {'axis_order': category_order, 'x': 0.0, 'y': 0.0},
        {'axis_order': category_order, 'x': math.cos(angle), 'y': math.sin(angle)},
    ])
    radar_label_records.append({
        'category': category,
        'x': 1.2 * math.cos(angle),
        'y': 1.2 * math.sin(angle),
    })
radar_axis_df = pd.DataFrame(radar_axis_records)
radar_label_df = pd.DataFrame(radar_label_records)

# Use Compute Atlas for the point layer: it provides facility-level coordinates,
# status, and source links. Limit it to data centers in the 50 states and DC.
atlas_path = Path(__file__).resolve().parent / 'data' / 'compute-atlas-facilities.csv'
atlas = pd.read_csv(atlas_path)
point_columns = {
    'name', 'operator', 'facility_type', 'status', 'confidence', 'city', 'state',
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

status_domain = ['operational', 'under_construction', 'permitted', 'proposed', 'cancelled']
unknown_statuses = sorted(set(points_df['status'].dropna()) - set(status_domain))
if unknown_statuses:
    raise ValueError(f'Unrecognized facility statuses in {atlas_path}: {unknown_statuses}')
points_df['status'] = points_df['status'].fillna('unknown')
status_domain.append('unknown')

show_points = alt.param(
    name='show_points',
    value=False,
    bind=alt.binding_checkbox(name='Show Compute Atlas data center locations '),
)
map_metric = alt.param(
    name='map_metric',
    value='Data center count',
)
metric_value_expression = (
    "map_metric === 'Land price' ? datum.land_price : "
    "map_metric === 'Commercial electricity price' ? datum.electricity_price : "
    "map_metric === 'Population' ? datum.population : "
    "datum.data_center_count"
)
metric_color_scheme = alt.ExprRef(
    expr=(
        "map_metric === 'County unemployment rate' ? 'oranges' : "
        "map_metric === 'Land price' ? 'greens' : "
        "map_metric === 'Commercial electricity price' ? 'oranges' : "
        "map_metric === 'Population' ? 'purples' : 'blues'"
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
    empty='all',
    clear='dblclick',
    on='click[!event.ctrlKey || length(data("selected_state_store")) < 4]',
    toggle='event.ctrlKey',
)

state_layer = alt.Chart(states).mark_geoshape(
    stroke='white',
    strokeWidth=0.5,
).encode(
    color=alt.condition(
        click,
        metric_color,
        alt.value('lightgray'),
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
        ],
    ),
).transform_calculate(
    metric_value=metric_value_expression,
).transform_filter(
    "map_metric !== 'County unemployment rate'"
)

counties = alt.topo_feature(data.us_10m.url, 'counties')
county_layer = alt.Chart(counties).mark_geoshape(
    stroke='white',
    strokeWidth=0.25,
).encode(
    color=alt.Color(
        'unemployment_percentile:Q',
        title='Unemployment percentile (US counties)',
        scale=alt.Scale(domain=[0, 100], scheme='oranges'),
        legend=None,
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
    click,
    empty=False,
).transform_calculate(
    metric_value=metric_value_expression,
)

point_layer = alt.Chart(points_df).mark_circle(
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
            range=['#238b45', '#ff7f0e', '#9467bd', '#1f77b4', '#7f7f7f', '#bdbdbd'],
        ),
        sort=status_domain,
    ),
    tooltip=[
        alt.Tooltip('name:N', title='Data center'),
        alt.Tooltip('company:N', title='Company'),
        alt.Tooltip('city:N', title='City'),
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
    'show_points'
)

detail_point_layer = alt.Chart(points_df).mark_circle(
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
            range=['#238b45', '#ff7f0e', '#9467bd', '#1f77b4', '#7f7f7f', '#bdbdbd'],
        ),
        sort=status_domain,
    ),
    tooltip=[
        alt.Tooltip('name:N', title='Data center'),
        alt.Tooltip('company:N', title='Operator'),
        alt.Tooltip('city:N', title='City'),
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
    'show_points'
).transform_filter(
    click,
    empty=False,
)

map_chart = alt.layer(state_layer, county_layer, point_layer).add_params(
    click
).project(
    type='albersUsa',
).properties(
    width=1150,
    height=560,
    title='US Overview (Select metric; click state/county, Ctrl+click up to 4 states)',
)

detail_map = alt.layer(detail_state_layer, detail_point_layer).project(
    type='mercator',
).properties(
    width=575,
    height=420,
    title='Selected State(s) Detail',
)

parallel_dimensions = [
    ('State', None),
    ('Data centers', 'data_center_count'),
    ('Land price ($/acre)', 'land_price'),
    ('Electricity (cents/kWh)', 'electricity_price'),
    ('Population', 'population'),
    ('Unemployment rate (%)', 'unemployment_rate'),
]
parallel_records = []
parallel_axis_records = []
parallel_tick_records = []
state_count = len(df)
state_positions = {
    row['state_name']: 0.98 - state_index * 0.96 / max(state_count - 1, 1)
    for state_index, (_, row) in enumerate(df.iterrows())
}

for dimension_index, (dimension, field) in enumerate(parallel_dimensions):
    parallel_axis_records.append({
        'axis_x': dimension_index,
        'dimension': dimension,
    })
    if field is None:
        for state_name, position in state_positions.items():
            parallel_records.append({
                'state_id': next(
                    state_id for state_id, name in state_name_by_id.items()
                    if name == state_name
                ),
                'state_name': state_name,
                'axis_x': dimension_index,
                'normalized_value': position,
                'data_center_count': None,
                'land_price': None,
                'land_price_note': None,
                'electricity_price': None,
                'population': None,
                'unemployment_rate': None,
            })
        continue

    minimum = float(df[field].min())
    maximum = float(df[field].max())
    if pd.isna(minimum) or pd.isna(maximum):
        raise ValueError(f'Missing values found for parallel-coordinate dimension {dimension}')
    value_range = maximum - minimum
    for _, row in df.iterrows():
        value = float(row[field])
        normalized_value = (
            0.02 + 0.96 * (value - minimum) / value_range
            if value_range
            else 0.5
        )
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
        })
        for tick_fraction in (0, 0.5, 1):
            tick_value = minimum + value_range * tick_fraction
            if field == 'land_price':
                tick_label = f'${tick_value / 1000:,.0f}k'
            elif field == 'electricity_price':
                tick_label = f'{tick_value:.1f}'
            elif field == 'unemployment_rate':
                tick_label = f'{tick_value:.1f}%'
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
parallel_state_labels = pd.DataFrame([
    {'state_name': state_name, 'normalized_value': position}
    for state_name, position in state_positions.items()
])
parallel_x_scale = alt.Scale(domain=[-0.6, 5.1], nice=False)
parallel_y_scale = alt.Scale(domain=[-0.04, 1.1], nice=False)

parallel_lines = alt.Chart(parallel_data).mark_line(
    opacity=0.28,
).encode(
    x=alt.X('axis_x:Q', scale=parallel_x_scale, axis=None),
    y=alt.Y('normalized_value:Q', scale=parallel_y_scale, axis=None),
    detail='state_name:N',
    order=alt.Order('axis_x:Q'),
    color=alt.condition(
        click,
        alt.Color(
            'state_name:N',
            title='Selected state',
            scale=alt.Scale(scheme='tableau20'),
        ),
        alt.value('#4b8b78'),
        empty=False,
    ),
    size=alt.condition(
        click,
        alt.value(6),
        alt.value(1.5),
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
    ],
).transform_filter(
    click
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
parallel_state_labels_chart = alt.Chart(parallel_state_labels).mark_text(
    align='right',
    baseline='middle',
    dx=-8,
    fontSize=8,
    color='#4c5552',
).encode(
    x=alt.X(datum=-0.02, scale=parallel_x_scale, axis=None),
    y=alt.Y('normalized_value:Q', scale=parallel_y_scale, axis=None),
    text='state_name:N',
)
parallel_chart = alt.layer(
    parallel_lines,
    parallel_axis_lines,
    parallel_tick_marks,
    parallel_tick_labels,
    parallel_dimension_labels,
    parallel_state_labels_chart,
).properties(
    width=1150,
    height=500,
    title=alt.TitleParams(
        text='Data Centers by State',
        subtitle=(
            f'States are alphabetical; numeric axes are scaled independently. '
            f'Latest data: land {latest_land_price_year}, electricity {latest_electricity_year}, '
            f'population {population_year}, unemployment 2025. Ctrl+click up to 4 states to compare; '
            f'double-click the map to clear.'
        ),
    ),
)

radar_x_scale = alt.Scale(domain=[-1.35, 1.35], nice=False, zero=False)
radar_y_scale = alt.Scale(domain=[-1.35, 1.35], nice=False, zero=False)
radar_grid = alt.Chart(radar_grid_df).mark_line(
    color='#d5d8dc',
    strokeWidth=1,
).encode(
    x=alt.X('x:Q', scale=radar_x_scale, axis=None),
    y=alt.Y('y:Q', scale=radar_y_scale, axis=None),
    detail='ring_rank:N',
    order=alt.Order('category_order:Q'),
)
radar_axes = alt.Chart(radar_axis_df).mark_line(
    color='#c6c9cc',
    strokeWidth=1,
).encode(
    x=alt.X('x:Q', scale=radar_x_scale, axis=None),
    y=alt.Y('y:Q', scale=radar_y_scale, axis=None),
    detail='axis_order:N',
)
radar_ring_labels = alt.Chart(pd.DataFrame({
    'x': [0, 0, 0, 0, 0],
    'y': [-0.2, -0.4, -0.6, -0.8, -1.0],
    'rank_label': ['20', '40', '60', '80', '100'],
})).mark_text(
    color='#777777',
    fontSize=10,
    dx=17,
    dy=0,
).encode(
    x=alt.X('x:Q', scale=radar_x_scale, axis=None),
    y=alt.Y('y:Q', scale=radar_y_scale, axis=None),
    text='rank_label:N',
)
radar_labels = alt.Chart(radar_label_df).mark_text(
    fontSize=12,
    fontWeight='bold',
    color='#333333',
).encode(
    x=alt.X('x:Q', scale=radar_x_scale, axis=None),
    y=alt.Y('y:Q', scale=radar_y_scale, axis=None),
    text='category:N',
)
radar_line = alt.Chart(radar_line_df).mark_line(
    color='#3c78b5',
    strokeWidth=2.5,
    point=alt.OverlayMarkDef(
        filled=True,
        fill='#3c78b5',
        stroke='white',
        size=75,
    ),
).encode(
    x=alt.X('x:Q', scale=radar_x_scale, axis=None),
    y=alt.Y('y:Q', scale=radar_y_scale, axis=None),
    color=alt.Color(
        'state_name:N',
        title='State',
        scale=alt.Scale(scheme='tableau20'),
    ),
    detail='state_name:N',
    order=alt.Order('category_order:Q'),
    tooltip=[
        alt.Tooltip('state_name:N', title='State'),
        alt.Tooltip('category:N', title='Category'),
        alt.Tooltip('value_label:N', title='Value'),
        alt.Tooltip('percentile_rank:Q', title='Percentile among states', format='.1f'),
        alt.Tooltip('value_note:N', title='Data note'),
    ],
).transform_filter(
    click,
    empty=False,
)
radar_chart = alt.layer(
    radar_grid,
    radar_axes,
    radar_ring_labels,
    radar_labels,
    radar_line,
).properties(
    width=575,
    height=420,
    title=alt.TitleParams(
        text='Selected State Profiles',
        subtitle='Percentile rank (0 center to 100 outer ring); compare up to four selected states.',
    ),
)

dashboard = (
    alt.vconcat(map_chart, parallel_chart, spacing=20)
    | alt.vconcat(detail_map, radar_chart, spacing=20)
).add_params(
    show_points,
    map_metric,
).configure_view(
    strokeWidth=0,
)
dashboard_path = Path(__file__).resolve().parent / 'data_center_dashboard.html'
dashboard.save(dashboard_path)
dashboard_html = dashboard_path.read_text(encoding='utf-8')
legend_metrics = {
    'Data center count': {
        'title': 'Data centers',
        'scheme': 'blues',
        'min': float(df['data_center_count'].min()),
        'max': float(df['data_center_count'].max()),
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
    'County unemployment rate': {
        'title': 'Unemployment percentile (US counties)',
        'scheme': 'oranges',
        'min': 0,
        'max': 100,
        'format': 'percentile',
    },
}
legend_metrics_json = json.dumps(legend_metrics)
style_marker = '      display: flex;\n'
embed_style_marker = (
    '    #vis.vega-embed {\n'
    '      width: 100%;\n'
    '      display: flex;\n'
)
if style_marker not in dashboard_html:
    raise ValueError('Could not find the dashboard container style to center the visualization')
dashboard_html = dashboard_html.replace(
    '  <style>\n',
    '  <style>\n'
    '    html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; }\n'
    '    body { display: flex; align-items: center; justify-content: center; }\n'
    '    #metric-menu {\n'
    '      position: fixed;\n'
    '      left: 12px;\n'
    '      top: 50%;\n'
    '      transform: translateY(-50%);\n'
    '      z-index: 10;\n'
    '      width: 190px;\n'
    '      padding: 14px;\n'
    '      background: rgba(255, 255, 255, 0.96);\n'
    '      border: 1px solid #d9dfdc;\n'
    '      border-radius: 8px;\n'
    '      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);\n'
    '      font: 14px/1.35 Arial, sans-serif;\n'
    '    }\n'
    '    #metric-menu h2 { margin: 0 0 8px; font-size: 14px; }\n'
    '    #metric-menu button {\n'
    '      display: block;\n'
    '      width: 100%;\n'
    '      padding: 8px 10px;\n'
    '      border: 0;\n'
    '      border-radius: 5px;\n'
    '      background: transparent;\n'
    '      color: #333;\n'
    '      text-align: left;\n'
    '      font: inherit;\n'
    '      cursor: pointer;\n'
    '    }\n'
    '    #metric-menu button:hover { background: #eef3f1; }\n'
    '    #metric-menu button[aria-pressed=\"true\"] {\n'
    '      background: #e1eee9;\n'
    '      color: #176b55;\n'
    '      font-weight: 700;\n'
    '    }\n'
    '    #map-legend {\n'
    '      position: fixed;\n'
    '      left: 55%;\n'
    '      top: 18%;\n'
    '      z-index: 10;\n'
    '      width: max-content;\n'
    '      padding: 0;\n'
    '      font: 12px/1.35 Arial, sans-serif;\n'
    '    }\n'
    '    #map-legend-title { display: block; margin-bottom: 8px; font-weight: 700; }\n'
    '    #map-legend-content { display: flex; align-items: stretch; gap: 8px; }\n'
    '    #map-legend-scale { width: 14px; min-height: 240px; border-radius: 3px; }\n'
    '    #map-legend-labels { display: flex; flex-direction: column; justify-content: space-between; }\n'
    '    @media (max-width: 900px) {\n'
    '      #metric-menu { left: 8px; top: 12px; transform: none; width: 160px; padding: 10px; }\n'
    '      #map-legend { left: 55%; top: 12px; width: max-content; padding: 0; }\n'
    '      #map-legend-scale { min-height: 180px; }\n'
    '    }\n',
    1,
)
if embed_style_marker not in dashboard_html:
    raise ValueError('Could not find the dashboard embed style to size the visualization')
dashboard_html = dashboard_html.replace(
    '  <div id="vis"></div>',
    '  <nav id="metric-menu" aria-label="Map metric">\n'
    '    <h2>Map metric</h2>\n'
    '    <button type="button" data-metric="Data center count" aria-pressed="true">Data center count</button>\n'
    '    <button type="button" data-metric="Land price" aria-pressed="false">Land price</button>\n'
    '    <button type="button" data-metric="Commercial electricity price" aria-pressed="false">Commercial electricity price</button>\n'
    '    <button type="button" data-metric="Population" aria-pressed="false">Population</button>\n'
    '    <button type="button" data-metric="County unemployment rate" aria-pressed="false">County unemployment rate</button>\n'
    '  </nav>\n'
    '  <aside id="map-legend" aria-live="polite">\n'
    '    <span id="map-legend-title"></span>\n'
    '    <div id="map-legend-content">\n'
    '      <div id="map-legend-scale"></div>\n'
    '      <div id="map-legend-labels"><span id="map-legend-max"></span><span id="map-legend-min"></span></div>\n'
    '    </div>\n'
    '  </aside>\n'
    '  <div id="vis"></div>',
    1,
)
embed_script = (
    '      vegaEmbed("#vis", spec, embedOpt)\n'
    '        .catch(error => showError(el, error));'
)
interactive_embed_script = (
    '      vegaEmbed("#vis", spec, embedOpt)\n'
    '        .then(({view}) => {\n'
    f'          const legendMetrics = {legend_metrics_json};\n'
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
    '          const updateLegend = metric => {\n'
    '            const item = legendMetrics[metric];\n'
    '            document.getElementById("map-legend-title").textContent = item.title;\n'
    '            document.getElementById("map-legend-scale").style.background =\n'
    '              "linear-gradient(to top, " + schemeColors[item.scheme].join(", ") + ")";\n'
    '            document.getElementById("map-legend-min").textContent = formatLegendValue(item.min, item.format);\n'
    '            document.getElementById("map-legend-max").textContent = formatLegendValue(item.max, item.format);\n'
    '            document.getElementById("map-legend-labels").setAttribute("aria-label",\n'
    '              formatLegendValue(item.min, item.format) + " to " + formatLegendValue(item.max, item.format));\n'
    '          };\n'
    '          updateLegend(view.signal("map_metric"));\n'
    '          document.querySelectorAll("#metric-menu button").forEach(button => {\n'
    '            button.addEventListener("click", () => {\n'
    '              view.signal("map_metric", button.dataset.metric).runAsync().then(() => {\n'
    '                updateLegend(button.dataset.metric);\n'
    '              });\n'
    '              document.querySelectorAll("#metric-menu button").forEach(option => {\n'
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
    ).replace(
        embed_style_marker,
        f'{embed_style_marker}      justify-content: center;\n'
        '      align-items: center;\n'
        '      width: 100vw;\n'
        '      height: 100vh;\n'
        '      overflow: hidden;\n'
        '      zoom: 1.3;\n',
        1,
    ),
    encoding='utf-8',
)
