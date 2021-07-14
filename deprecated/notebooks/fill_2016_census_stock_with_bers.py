# %%
import csv
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dublin_building_stock import join

data_dir = Path("../data")

# %% [markdown]
# # Get 2016 Dublin Small Area Boundaries
dublin_small_area_boundaries = gpd.read_file(
    data_dir / "dublin_small_area_boundaries.gpkg",
    driver="GPKG",
).loc[:, ["SMALL_AREA", "geometry"]]

# %% [markdown]
# # Get 2016 Small Area Statistics

# %%
column_names = {
    "T6_2_PRE19H": "before 1919",
    "T6_2_19_45H": "1919 - 1945",
    "T6_2_46_60H": "1946 - 1960",
    "T6_2_61_70H": "1961 - 1970",
    "T6_2_71_80H": "1971 - 1980",
    "T6_2_81_90H": "1981 - 1990",
    "T6_2_91_00H": "1991 - 2000",
    "T6_2_01_10H": "2001 - 2010",
    "T6_2_11LH": "2011 or later",
    "T6_2_NSH": "not stated",
    "T6_2_TH": "total",
}
columns = ["SMALL_AREA"] + list(column_names.values())
census_2016_amalgamated = (
    pd.read_csv(data_dir / "SAPS2016_SA2017.csv")
    .rename(columns=column_names)
    .assign(SMALL_AREA=lambda df: df["GEOGID"].str[7:])
    .loc[:, columns]
    .melt(id_vars="SMALL_AREA", var_name="period_built")
    .merge(dublin_small_area_boundaries["SMALL_AREA"])
    .assign(value=lambda df: df["value"].astype(np.int32))
)

# %%
census_2016 = (
    census_2016_amalgamated.reindex(
        census_2016_amalgamated.index.repeat(census_2016_amalgamated["value"])
    )  # Expand census to one building per row
    .drop(columns="value")
    .query("period_built != ['not stated', 'total']")
    .reset_index(drop=True)
    .assign(
        age_bin=lambda df: df["period_built"].replace(
            {
                "before 1919": "before 2001",
                "1919 - 1945": "before 2001",
                "1946 - 1960": "before 2001",
                "1961 - 1970": "before 2001",
                "1971 - 1980": "before 2001",
                "1981 - 1990": "before 2001",
                "1991 - 2000": "before 2001",
            }
        ),
        age_bin_total=lambda df: df.groupby(["SMALL_AREA", "period_built"]).transform(
            "count"
        ),
        category_id=lambda df: df.groupby(["SMALL_AREA", "age_bin"])
        .cumcount()
        .apply(lambda x: x + 1),  # add 1 to each row as cumcount starts at 0
        category_total=lambda df: df.groupby(["SMALL_AREA", "age_bin"]).transform(
            "count"
        ),
    )
)

# %% [markdown]
# # Get 09/06/2020 closed BER extract
# ... by special request from SEAI
# 325,545 buildings in Dublin as of 09/06/2020
# but only 281,400 successfully geocoded to SMALL_AREA
dublin_ber_closed = (
    pd.read_csv(
        data_dir / "BER.09.06.2020.csv",
        sep=",",
        low_memory=False,
        encoding="latin-1",
    )
    .loc[:, ["cso_small_area", "CountyName2", "Year of construction", "Energy Rating"]]
    .query("CountyName2.str.contains('DUBLIN') and cso_small_area.notnull()")
    .assign(
        period_built=lambda df: pd.cut(
            df["Year of construction"],
            bins=[-np.inf, 1919, 1945, 1960, 1970, 1980, 1990, 2000, 2010, np.inf],
            labels=[
                "before 1919",
                "1919 - 1945",
                "1946 - 1960",
                "1961 - 1970",
                "1971 - 1980",
                "1981 - 1990",
                "1991 - 2000",
                "2001 - 2010",
                "2011 or later",
            ],
        ),
        age_bin=lambda df: pd.cut(
            df["Year of construction"],
            bins=[-np.inf, 2000, 2010, np.inf],
            labels=[
                "before 2001",
                "2001 - 2010",
                "2011 or later",
            ],
        ),
        category_id=lambda df: df.groupby(["cso_small_area", "age_bin"])
        .cumcount()
        .apply(lambda x: x + 1),  # add 1 to each row as cumcount starts at 0
        energy_rating=lambda df: df["Energy Rating"].str[0],
    )
    .rename(columns={"cso_small_area": "SMALL_AREA"})
)

# %% [markdown]
# # Fill Census 2016 with BER Stock on matching SMALL_AREA, period_built

# %%
small_area_bers = census_2016.merge(
    dublin_ber_closed,
    how="left",
    on=["SMALL_AREA", "period_built", "age_bin", "category_id"],
)

# %%
valid_small_area_bers = small_area_bers.query("CountyName2.notnull()").assign(
    ber_category_total=lambda df: df.groupby(["SMALL_AREA", "period_built"])[
        "CountyName2"
    ].transform("count"),
)

# %%