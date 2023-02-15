# craigslist scraper

this is a python scraper for craigslist specifically. 

## usage

specify search critera in `.yaml` files. these are typically found by clicking around on craigslist, and seeing how the link changes for each addition

i.e. limiting mileage to 100k miles will result in the URL adding an `&max_auto_miles=100000`. To specify this, go to your yaml file and write
```
mode_name:
    search_filters:
        max_auto_miles: 100000
    refresh_rate: 5
```

In general you can look at the existing yamls, `cars.yaml`, to see how things work. 

The program is set up to run on my computer with chrome/windows webdriver. To do this:
```
conda activate base
python scrape.py cars.yaml --mode low_mileage_low_price_automatic
```

This will run the program. The email server is set up via an app password, which is saved to a text file at `drivers/app.pass`. Username/target email are configured in the yaml files, or with default arguments in the `scrape.py` `DEFAULT_YAML_ARGUMENTS` variable. 