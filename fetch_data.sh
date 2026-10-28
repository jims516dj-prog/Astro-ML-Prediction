#!/bin/sh
# Downloads the public source data into data/raw.
#   ./fetch_data.sh        everything (~65 MB): training matches + venue tables
#   ./fetch_data.sh live   venue tables only (~5 MB): enough for scripts/live.py
set -e
mkdir -p data/raw && cd data/raw
if [ "$1" != "live" ]; then
  curl -sSLO https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025/main/data/Matches.csv
fi
curl -sSL -o stadiums.csv https://raw.githubusercontent.com/jokecamp/FootballData/master/other/stadiums-with-GPS-coordinates.csv
curl -sSL -o csv-cities.csv.gz https://github.com/dr5hn/countries-states-cities-database/releases/latest/download/csv-cities.csv.gz
echo "data/raw ready"
