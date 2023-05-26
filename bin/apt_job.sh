#!/bin/bash
PATH=/usr/local/bin:/usr/local/sbin:~/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH
source /opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh
#eval "$(/opt/homebrew/bin/brew shellenv)"
conda activate base
cd /Users/luc/Documents/PROJECTS/craigs
python scrape.py -m all_0bedrooms -n 1 --no-email apts.yaml
python scrape.py -m all_1bedrooms -n 1 --no-email apts.yaml
python scrape.py -m all_2bedrooms -n 1 --no-email apts.yaml
python scrape.py -m rhodes_sfbay -n 1 music.yaml
python scrape.py -m nord_sfbay -n 1 music.yaml