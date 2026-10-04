from pathlib import Path
import math

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
mapped_count = int(us_facilities['state_abbr'].notna().sum())
unmapped_count = len(us_facilities) - mapped_count
coverage_note = (
    f'{mapped_count:,} of {len(us_facilities):,} US records assigned to a state/area; '
    f'{unmapped_count:,} with missing or unclear state excluded.'
)

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

radar_categories = ['Data centers', 'Land price', 'Electricity', 'Population']
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
            value_label = f'{value:,.0f} {unit}' if field != 'electricity_price' else f'{value:.2f} {unit}'
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
    bind=alt.binding_select(
        options=[
            'Data center count',
            'Land price',
            'Commercial electricity price',
            'Population',
        ],
        name='Map color: ',
    ),
)
metric_value_expression = (
    "map_metric === 'Land price' ? datum.land_price : "
    "map_metric === 'Commercial electricity price' ? datum.electricity_price : "
    "map_metric === 'Population' ? datum.population : "
    "datum.data_center_count"
)
metric_color_scheme = alt.ExprRef(
    expr=(
        "map_metric === 'Land price' ? 'greens' : "
        "map_metric === 'Commercial electricity price' ? 'oranges' : "
        "map_metric === 'Population' ? 'purples' : 'blues'"
    )
)
metric_color = alt.Color(
    'metric_value:Q',
    title='Selected map metric',
    scale=alt.Scale(scheme=metric_color_scheme),
)

# Load the US states topology and select states by their FIPS IDs.
states = alt.topo_feature(data.us_10m.url, 'states')
click = alt.selection_point(
    name='selected_state',
    fields=['state_id'],
    empty='all',
    clear='dblclick',
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
).transform_calculate(
    metric_value=metric_value_expression,
).add_params(
    click
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

map_chart = alt.layer(state_layer, point_layer).project(
    type='albersUsa',
).properties(
    width=600,
    height=400,
    title=alt.TitleParams(
        text='US Overview (Click a State to View Details)',
        subtitle=(
            f'{coverage_note} Click a state to populate the detail map. '
            f'Choose a map color metric above. Land values are USDA agricultural land '
            f'with buildings ($/acre), {latest_land_price_year}; Alaska and Hawaii use '
            'clearly labeled proxy estimates. Electricity uses commercial cents/kWh rates '
            f'from {latest_electricity_year} only; industrial prices are excluded. '
            f'Population is the Census Bureau {population_year} estimate. '
            'Double-click to clear the selection.'
        ),
    ),
)

detail_map = alt.layer(detail_state_layer, detail_point_layer).project(
    type='mercator',
).properties(
    width=600,
    height=400,
    title='Selected State Detail (select a state in the overview)',
)

bar_chart = alt.Chart(df).mark_bar().encode(
    x=alt.X('state_name:N', sort='-y', title='State', axis=alt.Axis(labelAngle=-45)),
    y=alt.Y('data_center_count:Q', title='Number of Data Centers'),
    color=alt.Color(
        'data_center_count:Q',
        title='Data centers',
        scale=alt.Scale(scheme='blues'),
    ),
    tooltip=[
        alt.Tooltip('state_name:N', title='State'),
        alt.Tooltip('data_center_count:Q', title='Data centers', format=','),
    ],
).transform_filter(
    click
).properties(
    width=600,
    height=500,
    title=alt.TitleParams(text='Data Centers by State', subtitle=coverage_note),
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
    width=500,
    height=500,
    title=alt.TitleParams(
        text='Selected State Profile',
        subtitle='Percentile rank (0 center to 100 outer ring); higher means a higher value.',
    ),
)

dashboard = (map_chart | detail_map) & (bar_chart | radar_chart)
dashboard = dashboard.add_params(show_points, map_metric).configure_view(strokeWidth=0)
dashboard.save(Path(__file__).resolve().parent / 'data_center_dashboard.html')
