#!/bin/sh
# Downloads the public source data into data/raw (≈65 MB).
set -e
mkdir -p data/raw && cd data/raw
curl -sSLO https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025/main/data/Matches.csv
curl -sSL -o stadiums.csv https://raw.githubusercontent.com/jokecamp/FootballData/master/other/stadiums-with-GPS-coordinates.csv
curl -sSL -o csv-cities.csv.gz https://github.com/dr5hn/countries-states-cities-database/releases/latest/download/csv-cities.csv.gz
echo "data/raw ready"
