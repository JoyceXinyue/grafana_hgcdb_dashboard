import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from tool.helper import *
from tool import AlertBuilder
from tool import AlertRuleValidator
from tool import DashboardValidator

"""
This script generates all alert JSON files, saves them to a folder under `grafana_hgcdb_dashboard`, and uploads them to Grafana.
Author: Xinyue (Joyce) Zhuang
"""

# Get the filelist from the config folder
filelist = os.listdir(CONFIG_FOLDER_PATH)

#Get the tablelist from the tool/postgres_table folder
tablelist = os.listdir(DB_INFO_PATH)

# Define the builder
alert_builder = AlertBuilder(GF_DS_UID)

# Delete all the alerts generated previously
client.delete_all_alert_rules()

# Define if success
succeed = True      # assume every file success 
failed_count = 0    # assume no file failed

# Loop for every config files
for config in filelist:

    # skip non-yaml files
    
    if config == "Other_Alerts_Config":
        # config file path
        config_path = os.path.join(CONFIG_FOLDER_PATH, config, "All_Table_Alerts_Config.yaml")
        config = "All_Table_Alerts_Config.yaml"
    elif not config.endswith(".yaml"):
        continue
    else:
        config_path = os.path.join(CONFIG_FOLDER_PATH, config)

    dashboardValidator = DashboardValidator(config_path)
    
    # Load the alerts
    with open(config_path, mode = 'r') as file:
        tot_config = yaml.safe_load(file)
        # check if alerts exist:
        print(config_path)
        if "alert" not in tot_config:
            continue
        # load alerts
        alerts = tot_config["alert"]
    
    # try:
    #     validator = AlertRuleValidator(config_path)
    #     print(f"\n[VALIDATING] Checking if the alert rules in the config file: <{config}> is valid...")
    #     valid_alerts = []
    # except FileNotFoundError as e:
    #     print(f"[ERROR] {e}")
    #     continue
        
    # Loop for every alert
    for idx, alert in enumerate(alerts):
        alert_title = alert.get("title", f"<Alert {idx}>")
        # ok = validator.check_single_alert(idx, alert)

        # if not ok:  # skip invalid config file
        #     print(f"[WARNING] Validation failed for config: <{config}>. Skipping this file.\n")
        #     succeed = False
        #     failed_count += 1
        #     continue
        
        # Generate the alert json
        folder_name = config.split(".")[0].replace("_", " ")
        if folder_name == "All Table Alerts Config":
            title = alert["title"]
            for table in tablelist:
                alert["title"] = title
                alert["table"] = table[:-4]
                if alert["table"] == "module_info":
                    # We don't want to generate/upload "module_info" table
                    continue
                alert["title"] = alert["title"] + ":" + alert["table"]
                columns = dashboardValidator.get_valid_columns(alert["table"])
                if alert["parameter"] in columns:
                    alert["sql"] = alert_builder.generate_missing_xml_sql(alert["table"],columns,alert["parameter"],alert["conditions"],alert["ignore_columns"])
                    alert_json = alert_builder.generate_alerts(alert, folder_name)

                    # Export the alert json to a file
                    file_name = config.split(".")[0]
                    alert_builder.save_alerts_json(alert, alert_json, file_name)
            continue

        alert_json = alert_builder.generate_alerts(alert, folder_name)

        # Export the alert json to a file
        file_name = config.split(".")[0]
        alert_builder.save_alerts_json(alert, alert_json, file_name)

if succeed:
    print(" >>>> All Alerts json generated successfully!\n")
else:
    print(f" >>>> {failed_count} Alerts json failed to generate. \n")


# Upload alerts
try:
    folder_list = os.listdir("./Alerts")
    for folder in folder_list:
        file_list = os.listdir(f"./Alerts/{folder}")
        for file_name in file_list:
            if file_name.endswith(".json"):
                file_path = f"./Alerts/{folder}/{file_name}"
                try:
                    alert_builder.upload_alerts(file_path)
                except Exception as e:
                    print(f"[SKIPPED] Error uploading alert rule: {file_name} | Status: {e}")

    print("\n >>>> Alerts json files uploaded!\n")

except:
    print("\n >>>> Alerts json files not found...\n")


# clear all the notification rules and contact points
client.delete_notification_policy_tree()
client.delete_all_contact_points()

# get file:
try:
    contact_filelist = os.listdir(CONTACT_FOLDER_PATH)
except:
    print(f"Contact config folder not found: {CONTACT_FOLDER_PATH}")

for config in contact_filelist:
    contact_path = os.path.join(CONTACT_FOLDER_PATH, config)

    with open(contact_path, 'r') as f:
            config = yaml.safe_load(f)

    for cp in config.get("contactPoints", []):
        client.create_contact_point(cp["name"], cp["addresses"])

    # upload notification policy (contact points)
    tree = config.get('policies')[0]
    client.put_policy_tree(tree)

    print("\n >>>> Notification system uploaded!\n")


# Clear GF_FOLDER_UIDS and GF_ALERT_UIDS map:
gf_conn.set("GF_FOLDER_UIDS", {})
gf_conn.set("GF_ALERT_UIDS", {})
gf_conn.save()
gf_conn.reload()
print(" >>>> GF_FOLDER_UIDS and GF_ALERT_UIDS map cleared!\n")

# Delete the alert files
remove_folder("Alerts", ALERTS_FOLDER_PATH)
print("\n >>>> Alerts json files removed!\n")