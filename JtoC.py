from pickle import FALSE
import pandas as pd
import datetime
import pytz
import os
import json
import shutil
import pathlib
import re

tz = pytz.timezone('US/Central')  
ct_start = datetime.datetime.now(tz) 
print("script started at:", ct_start)


#### CONFIGURABLE VARIABLES
SchemaName = "EDA" # select based on Cookbook syntax
JSONname = "example-output.json" # based on input file
tableListJSON = "TableList.json" # config input file name


#### FUNCTIONS
# Used for each "picklist" to return a list of "labels - values" sep. by \n
def picklistLabels(br):
    if not br:
        return "no values"
    if len(br) > 100: # ideally the output should be legible -- for our org most of these are lists of countries / other objects in SF
        return "100+ values"
    v = ''
    for d in br: 
        if d["active"] == True:
            v = v + str(d["label"]) + " - " + str(d["value"])+ "\n"
    return v.rstrip()
# Used to identify primary keys
def PKfinder(row):
    if row["type"] == "id" :
        return "TRUE"
    return ''
# Used to convert to Data Cookbook "column" vs. "id" type -- Since Indexes can't be linked to in Diagram, making those Columns/PKs
#def getType(row):
    if row["type"] == "id":
        return "Index"
    return "Column"
# Used to get type
def getType(row):
    if row["calculated"]:
        return row["type"] + " (calculated)"
    return row["type"]
# Used to reduce reference column to first entry -- not ideal but DC's 
# ERP diagram/linking only works with one table referenced per FK
def getRef(row):
    if "User" in str(row["referenceTo"]):
        return "User"    # picking User over other objects to handle User, Group as assigned to keys (org always uses User)
    if "Contact" in str(row["referenceTo"]):
        return "Contact" # picking Contact over other objects to handle Lead, Contact situation (org almost always uses Contact)
    return str(row["referenceTo"]).split()[0].replace("'","").replace("[","").replace("]","").replace(",","") # from SF some objects point at all other objects -- which breaks cookbook
# Sets "Id" as Ref Col to reflect SF convention
def getRefCol(row):
    if len(str(row["referenceTo"])) > 2 :
        return "Id"
    return ''
# sets SchemaName as Reference Model for Data cookbook processing
def getRefModel(row):
    if len(str(row["referenceTo"])) > 2 :
        return SchemaName
    return ''
# Sets "Comment" field for Cookbook, which here contains help text + picklist vals (helpful for our org) 
def commentMaker(row, dict, RecordTypes):
    global AKList
    pl = ""
    ht = ""
    fm = ""
    # logging if Alternate Key
    if ((row["type"]!="id") & (row["nillable"] == True) & (row["unique"] == True)):
            AKList = row["name"] + ", " + AKList
    # making comment
    if (row["type"] == "picklist") | (row["type"] == "multipicklist"):
        pl = "Picklist Items: " + picklistLabels(dict[table]["fields"][row["name"]]["picklistValues"]) # gets list of values sep by \n, to be cleaned later
    if ( (row["name"]=="RecordTypeId") & (len(RecordTypes.index) != 0) ):
        pl = "Record Type IDs - Developer Names: " + ' / '.join(RecordTypes["keyList"]) # gets list of values sep by /
    if row["inlineHelpText"] is not None:
        ht = "Help Text: " + str(row["inlineHelpText"]) + " | " 
    if row["calculated"]:
        fm = "Formula: " + str(row["calculatedFormula"]) + " | "
    val = (ht + fm + pl).replace("\n","/")[:1000].strip(" | ")
    return re.sub(r'(?<=[.,])(?=[^\s])', r' ', val) 


### FOLDER SETUP
#open JSON
os.chdir(os.path.dirname(os.path.abspath(__file__)))
f = open(JSONname)
sch = json.load(f)
f2 = open(tableListJSON)
tableList = json.load(f2)

# making directories
pathlib.Path("unaltered").mkdir(parents=True, exist_ok=True) 
pathlib.Path("DFformat").mkdir(parents=True, exist_ok=True) 
pathlib.Path("picklists").mkdir(parents=True, exist_ok=True) 

### REFORMATTING JSON 
dfU = None
dfPL = None
for table in sch.keys():
    tcomment = '' # can be used to set table comment -- org specific plan for this
    AKList = ''
    RecordTypes = pd.DataFrame()

    if len(sch[table]["recordTypeInfos"]) > 2 :
        RecordTypes = pd.DataFrame.from_dict(sch[table]["recordTypeInfos"])
        RecordTypes["keyList"] = RecordTypes["recordTypeId"] + " - " + RecordTypes["developerName"] 
        #print(RecordTypes["keyList"])
    #print("Formatting " + table)  #debugging, seems to cost about 1 sec/100 tables 

    ### used to create csv from JSON raw data, for better legibility. CSVs will be zipped
    fields = pd.DataFrame.from_dict(sch[table]["fields"], orient='index')
    fields.to_csv("unaltered/unalt____" + table + ".csv")
    
    if len(fields.index) < 2:  # cookbook won't take tables with only an "Id" column (unclear why they exist in SF anyhow)
        continue
    
    ### used to create CSV of all picklists with active values
    Pfields = fields.loc[(fields["type"] == "picklist") | (fields["type"] == "multipicklist")]
    if len(Pfields.index) != 0:
        dfPLi = pd.DataFrame({"Parent Object": table,
                            "Field Name": Pfields["name"],
                            "Field Label": Pfields["label"],
                            "Type": Pfields["type"],
                            "Help Text": Pfields["inlineHelpText"],
                            "Label - Value": Pfields.apply(lambda row: picklistLabels(sch[table]["fields"][row["name"]]["picklistValues"]), axis=1)  
                            })
    if dfPL is None: 
            dfPL = dfPLi
    else: 
            dfPL = pd.concat([dfPL, dfPLi], axis=0, ignore_index=True)

    ### used to create CSV for the data cookbook
    ### cols/orders/etc. all as per data cookbook spec -- https://stthomas.datacookbook.com/doc/Data_Cookbook_User_Guide.pdf#page=141
    ## create df for all of the fields associated with the object
    dfKids = pd.DataFrame({"Schema": SchemaName, 
                        "Object Type": "Column", #fields.apply(lambda row: getType(row), axis=1), 
                        "Object Name":fields["name"],
                        "Parent Object Type":"Table",
                        "Parent Object Name":table,
                        "Row Count":'',
                        "Comment":fields.apply(lambda row: commentMaker(row, sch, RecordTypes), axis=1),#### use later for ODS / SF conversion?
                        "Data Type":fields.apply(lambda row: getType(row), axis=1),
                        "Length": fields["length"],
                        "Primary Key":fields.apply(lambda row: PKfinder(row), axis=1),
                        "Precision":'',
                        "Scale":'',
                        "Nulls Allowed":fields["nillable"],
                        "Columns":'',
                        "Code":'',
                        "Unique": fields.apply(lambda row: PKfinder(row), axis=1), # indexes only
                        "Foreign Key Name":fields["relationshipName"],
                        "Reference Model": fields.apply(lambda row: getRefModel(row), axis=1), #FKs only
                        "Reference Table": fields.apply(lambda row: getRef(row), axis=1), #FKs only
                        "Reference Column": fields.apply(lambda row: getRefCol(row), axis=1) #FKs only
                        })
    ## Create row for the table object/comment/etc. 
    if table in tableList.keys():
        tcomment = "ODS (https://stthomas.datacookbook.com/institution/data_systems/5044/schemas/2181) table name: " + tableList[table] + " | " # set for table -- org specific plan for this one
    if len(RecordTypes.index)!=0:
        tcomment = tcomment  + "Possible Record Types (Controlled by RecordTypeId for Each Record): " + ', '.join(RecordTypes["developerName"]) + " | "
        tcomment.strip(" | ")
    if (AKList != ''):
        tcomment = tcomment + "Alternate Keys: " + AKList.strip(", ")
        tcomment.strip(" | ")
    dfParent = pd.DataFrame({"Schema": SchemaName, # depends on DC syntax
                "Object Type": ["Table"], 
                "Object Name":table,
                "Parent Object Type":["Schema"],
                "Parent Object Name": SchemaName,
                "Row Count":'',
                "Comment": tcomment
                })

    if dfU is None: 
        dfU = pd.concat([dfParent, dfKids], axis=0, ignore_index=True)
    else: 
        dfU = pd.concat([dfU, dfParent], axis=0, ignore_index=True)
        dfU = pd.concat([dfU,dfKids], axis=0, ignore_index=True)


### SAVING OUTPUT
dfU.to_csv("DFformat/" + SchemaName + ".csv", index=False)
dfPL.to_csv("picklists/PicklistSpecs.csv", index=False)
shutil.make_archive("JSON_fields_unaltered", 'zip', "unaltered")

ct_end = datetime.datetime.now(tz) 
print("script ended at:", ct_end)
print("total script run time: " + str(ct_end - ct_start))