# Grafana_HGCDB_Dashboard ε=ε=(<ゝω・)☆
This is a dashboard provided by [Grafana](https://github.com/grafana/grafana?tab=readme-ov-file) to monitor the HGC Postgres database.  
Chinese Version README: [读我.md](a_EverythingNeedToChange/读我.md)

**Developers**:   
-Siyu (Rain) Chen: Overall structure and Dashboards  
-Xinyue (Joyce) Zhuang: Alert System  
With support from the entire CMU HGCal MAC.

**Example**:
[CMU Dashboards](https://cmuhgcdashboard.phys.cmu.edu:3000/dashboards)

## Before Run 
1. Download Grafana.
- [Get Grafana](https://grafana.com/get)

In `Get Grafana` page, choose `OSS` instead of `Cloud`. Download the Grafana by your operating system. The version I used is `v12.0.0`.  

The default port is `localhost:3000` and the default URL is http://localhost:3000.
- default Grafana username: `admin`
- defualt Grafana password: `admin`

2. Check and Run `create_config.py` to generate the configuration files for Grafana and connection to database.
```
python create_config.py
```
- The `db_conn.yaml` file is the configuration file for database connection.
- The `gf_conn.yaml` file is the configuration file for Grafana connection.

3. Start the Grafana server by running the following command:
```
sudo systemctl status grafana-server
```
- More Info: [Start Grafana](https://grafana.com/docs/grafana/latest/setup-grafana/start-restart-grafana/)

4. Modify the access for anonymous visit to Grafana:
- For Linux, the configuration file path should be '/etc/grafana/grafana.ini'
- Modify the `auth.anonymous` section to `enabled = true`, for example:
```
[auth.anonymous]
enabled = true

# Organization name that should be used for unauthenticated users
org_name = Main Org.

# Role for unauthenticated users, other valid values are `Editor` and `Admin`
org_role = Viewer

# Hide the Grafana version text from the footer and help tooltip for unauthenticated users (default: false)
hide_version = true

# Setting this limits the number of anonymous devices in your instance. Any new anonymous devices added after the limit has been reached will be denied access.
device_limit =
```
- More Info: [Grafana Anonymous Access](https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/anonymous-auth/)

5. Set the SMTP server for Grafana email notification:
- For lab use:
  - Please contact the IT department to set the lab server as an email sender and modify the same configuration file accordingly.
- For personal/developing perpose:
  - In the same configuration file, modify the `smtp` section to set the SMTP server:
```            
[smtp]
enabled = true
host = smtp.gmail.com:587 # Gmail SMTP server
user =          # your gmail account - usually is the same one as your email address
# If the password contains # or ; you have to wrap it with triple quotes. Ex """#password;"""                                                                                                               
password =      # application password - see attached link below
cert_file =
key_file =
skip_verify = false
from_address =       # the email address to send from
from_name = Grafana
ehlo_identity =
startTLS_policy =
enable_tracing = false
```
- More Info on SMTP Configuration: [Grafana SMTP Configuration](https://grafana.com/docs/grafana-cloud/alerting-and-irm/alerting/configure-notifications/manage-contact-points/integrations/configure-email/)
- More Info on application password: [Google Application Password](https://support.google.com/accounts/answer/185833?hl=en)

6. Restart the Grafana server by running the following command:
```
sudo systemctl restart grafana-server
```

## Run Steps
1. Run `main.py` to generate the dashboards to Grafana.
```
python main.py
```

## To add a new dashboard/alert rule
- [Details here](config_folders/README.md)

## Files and Folders Inventory:
- Files:
    - `main.py`: The main script to generate and upload the dashboards to Grafana.
    - `create_config.py`: The script to generate the configuration files for Grafana and connection to database.
- Folders:
    - `config_folders`: contains all the configuration files for Grafana.
    - `create`: contains all the files to create the dashboards.
    - `preSteps`: contains all the scripts to get the API_KEY and add the database_source.
    - `tool`: contains all the scripts that are used to generate `json` files to Grafana.


## How the Scripts Work
The `preSteps` folder will only be runned for once, as there's a parameter - `GF_RUN_TIMES` - in `gf_conn.yaml` (please make sure it is set to 0 before the first time running the main.py) counting how many times the `main.py` has been runned:  
- `preSteps` folder:  
    - `get_api_key.py` is the script to create a service account and get the API_KEY for Grafana. The API_KEY will be stored in the `gf_conn.yaml` file for future usages: add datasource, create folders, and upload dashboards.
    - `add_datasource.py` is the script to add the database_source to Grafana. The database_source is called from the parameters in the `db_conn.yaml` file, which will be generated by `create_config.py`.
    - More information about [Grafana API](https://grafana.com/docs/grafana/latest/developers/http_api/)
- `create` folder:
    - `create_alerts.py`: create and upload the alerts for the dashboards. The generated alerts json files are stored in the `Alerts` folder.
    - `create_dashboards.py`: create and upload the dashboards to Grafana. The generated dashboards json files are stored in the `Dashboards` folder.
    - `create_folders.py`: create the folders for the dashboards in Grafana.
- `tool` folder:
    - `dashboard_builder.py` contains the class to handle all the functions for the dashboards.
    - `helper.py` is the script than contain classes to load the configuration files: `ConfigLoader` and handle the API requests: `GrafanaClient`, and some other helper functions, e.g.: `create_uid`, and loaded info from the configuration files.
    - `other_builder.py` is the script to build the other featurers, e.g.: `Filters`, `Alerts`...
    - `panel_builder.py` is the script to build the panels for each dashboard, the panel types are: General SQL panels, and IV_Curve plot.
    - `sql_builder.py` is the script to build the SQL queries for each panel. I used `ABC` - Abstract Base Class - to build the SQL queries for different chart types. For the future developers who want to add more chart types, they can simply add a new class and implement the chart types in the `ChartSQLFactory` class. The Class is called only in: `panel_builder.py`: line 31 - line 40 to generate the SQL queries for each panel.
    - More information about [JSON MODEL](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/view-dashboard-json-model/) for Grafana dashboards.
  
Thanks for reading and using my scripts! If you have any questions, please feel free to ask me, and I'm happy to hear any suggestions or improvements! 

## To Remove the unwanted dashboards
1. Open the logged in Grafana Web UI.
2. Select the dashboards/folders you want to remove.
3. Click the `Delete` button.
4. Confirm the deletion - Type the `Delete` word in the input box.

## To Remove the unwanted alert-rules
1. Run `delete_alert_rule.py`
```
python delete_alert_rule.py
```
2. Choose and enter the `alert rule UID` you would like to delete.
3. Press `Enter`