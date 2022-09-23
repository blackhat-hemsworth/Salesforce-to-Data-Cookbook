# Salesforce JSON Conversion for Data Governance

This Python script is applied to Salesforce JSON schema output, specifically the kind produced by [Katie Kode's CCI project](https://github.com/kkgthb/download-salesforce-objects-and-fields-as-json), in order to:

1. Format a large single .csv such that it can be read by the iData Cookbook, which has a [specific schema](https://stthomas.datacookbook.com/doc/Data_Cookbook_User_Guide.pdf#page=141). This format is also probably handy in non-Cookbook specific contexts, but you might do well to un-replace the "\n" characters. 

2. Output a .zip file of .csv's corresponding to the "fields" of the JSON, with attributes unaltered (for easier legibility than with the JSON).

3. Produce another .csv that contains help text and picklist values for all picklists (since this information will not be formatted ideally within the data cookbook).

# Setup

All you need is a JSON file in the [correct format](https://github.com/kkgthb/download-salesforce-objects-and-fields-as-json) (placed in the main folder) and some way to run a Python script. 
