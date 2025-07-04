import os

import asyncio
import base64
import datetime

import asyncpg
from PIL import Image
from matplotlib import pyplot as plt

from tool.helper import *
from tool.builders.sql_builder import ChartSQLFactory, BaseSQLGenerator

"""
This file defines the class for building the panels json file in Grafana.
    - General Panels
    - IV Curve Plot
"""

class PanelBuilder:
    def __init__(self, datasource_uid):
        self.datasource_uid = datasource_uid
        self.SQLgenerator = BaseSQLGenerator()
    
    # -- Regular Panels --
    def generate_sql(self, chart_type: str, table: str, condition: str, groupby: list, filters: list, distinct: bool) -> str:
        """Generate the SQL command from ChartSQLFactory. -> sql_builder.py
        """
        # Get Generator
        generator = ChartSQLFactory.get_generator(chart_type)

        # Generate SQL command
        panel_sql = generator.generate_sql(table, condition, groupby, filters, distinct)

        return panel_sql

    def assign_gridPos(self, dashboard_title: str, config_panels: list, max_cols=24) -> list:
        """Assign gridPos to each panel in the dashboard. 
        """
        # initial settings
        x, y = 0, 0

        # set up the size of each panel
        num_panels = len(config_panels)

        # set up the max number of panels per line:
        if dashboard_title.startswith("Free") or "Module Assembly" in dashboard_title or 'IV_Curve Plot' in dashboard_title:
            max_num = 1
        elif dashboard_title == "Module Info" or "Environment Monitoring" in dashboard_title:
            max_num = 2
        else: 
            max_num = 3

        # assign width and hight    
        if num_panels <= max_num:
            width = max_cols // num_panels
        else:
            width = max_cols // max_num

        height = width // 2 + 2

        # assign gridPos to each panel
        for panel in config_panels:
            if x + width > max_cols:    # Switch lines
                x = 0
                y += height

            panel["gridPos"] = {
                "x": x,
                "y": y,
                "w": width,
                "h": height
            }

            x += width

        return config_panels

    def get_info(self, panel: dict, chart_type: str) -> tuple:
        """Get the information from the panel config by chart_type.
        """
        if chart_type == "text":
            year = panel.get("year", None)
            month = panel.get("month", None)
            day = panel.get("day", None)

            if year and month and day:
                time = f"{year}-{month}-{day}"
            else:
                time = str(datetime.datetime.now()).split(' ')[0]

            return time
        
        elif chart_type == "xychart":
            filters = panel.get("filters", None)
            temp_condition = panel.get("temp_condition", None)
            rel_hum_condition = panel.get("rel_hum_condition", None)
            gridPos = panel.get("gridPos")
            
            return filters, temp_condition, rel_hum_condition, gridPos
        
        else:
            title = panel.get("title")
            table = panel.get("table")
            condition = panel.get("condition")
            groupby = panel.get("groupby")
            filters = panel.get("filters")
            gridPos = panel.get("gridPos")
            distinct = panel.get("distinct")
            return title, table, condition, groupby, filters, gridPos, distinct
    
    def generate_general_panel(self, title: str, raw_sql: str, table: str, chart_type: str, gridPos: dict) -> dict:
        """Generate a panel json based on the given title, raw_sql, table, chart_type, and gridPos.
        """
        # generate the panel json:
        panel_json = {
        "datasource": {
            "type": "grafana-postgresql-datasource",
            "uid": f"{self.datasource_uid}"
        },
        "fieldConfig": {
            "defaults": {
            "color": {
                "mode": "palette-classic"
            },
            "custom": {
                "scaleDistribution": {
                "type": "linear"
                },
            },
            "mappings": [],
            },
            "overrides": []
        },
        "gridPos": gridPos,
        "id": 1,
        "options": {
            "barRadius": 0,
            "barWidth": 0.97,
            "fullHighlight": False,
            "groupWidth": 0.7,
            "legend": {
            "calcs": [],
            "displayMode": "list",
            "placement": "bottom",
            "showLegend": True
            },
            "orientation": "horizontal",
            "showValue": "auto",
            "stacking": "normal",
            "tooltip": {
            "hideZeros": False,
            "mode": "single",
            "sort": "none"
            },
            "xTickLabelRotation": 0,
            "xTickLabelSpacing": 0
        },
        "pluginVersion": "12.0.0",
        "targets": [
            {
            "datasource": {
                "type": "grafana-postgresql-datasource",
                "uid": f"{self.datasource_uid}"
            },
            "editorMode": "code",
            "format": "table",
            "rawQuery": True,
            "rawSql": f"{raw_sql}",
            "refId": "A",
            "table": f"{table}"
            }
        ],
        "title": f"{title}",
        "transformations": [
            {
            "id": "filterFieldsByName",
            "options": {}
            }
        ],
        "type": f"{chart_type}"
        }

        return panel_json
    
    # -- IV Curve Plot --
    def generate_IV_curve_panel(self, title: str, content: str) -> dict:
        """Generate the panel specifially for IV_curve plot.
        """
        # generate the panel json:
        panel_json = {
        "fieldConfig": {
            "defaults": {},
            "overrides": []
        },
        "gridPos": {        
            "h": 14,
            "w": 14,
            "x": 0,
            "y": 0
        },
        "id": 7,
        "options": {
            "code": {
            "language": "plaintext",
            "showLineNumbers": False,
            "showMiniMap": False
            },
            "content": content,
            "mode": "markdown"
        },
        "pluginVersion": "12.0.0",
        "title": title,
        "type": "text"
        }

        return panel_json

    def generate_plot(self, time: str, TIMEOUT=5) -> str:
        """Generate the IV_curve Plot.
           Author: Andrew C. Roberts  
        """
        loop = asyncio.get_event_loop()
        
        async def connect_db():
            return await asyncpg.create_pool(
                host = DB_HOST,
                database = DB_NAME,
                user = DB_USER,
                password = DB_PASSWORD
            )

        # try connecting to db
        try:
            pool = loop.run_until_complete(asyncio.wait_for(connect_db(), timeout=TIMEOUT))

        except asyncio.TimeoutError:
            print(f"[ERROR] Failed to connect to database: Timeout after {TIMEOUT} seconds.")
            raise

        except Exception as e:
            print(f"[ERROR] Failed to connect to database: {str(e)}")
            raise

        # get time info
        time_arg = f"AND module_iv_test.date_test <= '{time}'"

        # functions for interating with db
        async def fetch_modules(pool):
            query = f"""SELECT DISTINCT ON (module_info.module_name) * 
                        FROM module_info
                        LEFT JOIN module_iv_test ON module_info.module_name = module_iv_test.module_name
                        WHERE 
                            module_info.module_name IS NOT NULL
                            {time_arg}"""
            async with pool.acquire() as conn:
                return await conn.fetch(query)

        async def fetch_iv(pool, moduleserial):
            query = rf"""SELECT *  
                        FROM module_iv_test                                                                  
                        WHERE 
                            REPLACE(module_name,'-','') = '{moduleserial}'
                            AND (rel_hum ~ '^[-+]?[0-9]+(\.[0-9]+)?$')
                            AND (temp_c ~ '^[-+]?[0-9]+(\.[0-9]+)?$') 
                            {time_arg}                     
                        ORDER BY date_test, time_test;"""
            async with pool.acquire() as conn:
                return await conn.fetch(query)
 

        def select_iv(moduleserial, modulestatus, dry=True, roomtemp=True):
            result = loop.run_until_complete(fetch_iv(pool, moduleserial))
            
            runs = []
            for r in result:
                RH = float(r['rel_hum'])
                T = float(r['temp_c'])
                req1 = (RH <= 12) if dry else (RH >= 20)
                req2 = (T >= 10 and T <= 30) if roomtemp else (T <= -20)
                if req1 and req2 and r['status_desc'] == modulestatus:
                    runs.append(r)

            return runs

        result = loop.run_until_complete(fetch_modules(pool))

        def modserkey(module):
            return int(module['module_no'])

        result.sort(key=modserkey)
        module_serials = [mod['module_name'] for mod in result]
        modules = module_serials[-N_MODULE_SHOW:]

        fig, ax = plt.subplots(figsize=(16, 12))

        datetoday = str(datetime.datetime.now()).split(' ')[0]

        def sortkey(curve):
            return curve['meas_i'][-1]/curve['program_v'][-1]

        dry = True
        for module in modules:

            curvedata = select_iv(module, 'Completely Encapsulated', dry=dry, roomtemp=True)

            if len(curvedata) == 0:
                curvedata = select_iv(module, 'Frontside Encapsulated', dry=dry, roomtemp=True)

            if len(curvedata) > 0:
                # get best curve
                curvedata.sort(reverse=True, key = sortkey)
                
                meas_v = curvedata[-1]['meas_v']
                meas_i = curvedata[-1]['meas_i']

                plt.plot(meas_v, meas_i, label=module)
                        
        ax.set_yscale('log')
        dryname = 'Dry' if dry else 'Ambient'
        ax.set_title(f'{dryname} Module IV Curves [Log Scale] - test before {time}', fontsize=30)
        ax.set_xlabel('Reverse Bias [V]', fontsize=25)
        ax.set_ylabel(r'Leakage Current [A]', fontsize=25)
        ax.set_ylim(1e-9, 1e-03)
        ax.set_xlim(0, 500)
        ax.xaxis.label.set_size(30)
        ax.yaxis.label.set_size(30)
        ax.tick_params(axis='both', which='major', labelsize=25)
        ax.legend(fontsize=15, loc='upper left')

        # create folder:
        os.makedirs("IV_curves_plot", exist_ok=True)
        # define path and save plot
        plt_path = f'IV_curves_plot/combined_iv_logscale_{datetoday}_{N_MODULE_SHOW}.png'
        plt.savefig(plt_path)

        return plt_path

    def convert_png_to_base64(self, image_path: str) -> str:
        """Convert the png to base64
        """
        # Compress the image
        img = Image.open(image_path)
        img = img.convert("P", palette=Image.ADAPTIVE, colors=256)
        img.save(image_path, optimize=True)

        # Generate the encoded_string
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded_string

    def generate_content(self, encoded_string: str) -> str:
        """Generate the markdown content for text panel
        """
        content = f'<img src=\"data:image/png;base64,{encoded_string}" style="width: auto; height: auto;"/>'
        return content
    
    # -- IV Curve Plot Version 2.0 --
    def IV_curve_panel_filter(self, filters: dict) -> str:
        """Build the WHERE clause for IV curve plot based on the given filters.
        """
        module_where_clauses = []
        iv_where_clauses = []

        for filter_table, _ in filters.items():
            if filter_table == "module_info":
                for elem in filters[filter_table]:
                    arg = self.SQLgenerator._build_filter_argument(elem, filter_table)
                    module_where_clauses.append(arg)
                    module_where_arg = " AND ".join(module_where_clauses)
            elif filter_table == "module_qc_summary":
                for elem in filters[filter_table]:
                    arg = self.SQLgenerator._build_filter_argument(elem, filter_table)
                    iv_where_clauses.append(arg)
                    iv_where_arg = " AND ".join(iv_where_clauses)

        return module_where_arg, iv_where_arg

    def IV_curve_panel_sql(self, filters: dict, temp_condition: str, rel_hum_condition: str, N_MODULE_SHOW="${N_MODULE_SHOW}") -> str:
        """Generate the SQL command for IV curve plot based on temp_condition and rel_hum_condition.
        """
        # build the WHERE clause
        module_where_arg, iv_where_arg = self.IV_curve_panel_filter(filters)

        # generate the SQL command
        raw_sql = f"""
        WITH selected_iv_test AS (
        SELECT module_iv_test.*
        FROM module_iv_test
        JOIN module_qc_summary ON module_iv_test.module_name = module_qc_summary.module_name
        WHERE {iv_where_arg}
        ),

        selected_modules AS (
        SELECT 
            module_info.module_name
        FROM module_info
        WHERE {module_where_arg}
            AND $__timeFilter(test_iv) 
            AND test_iv IS NOT NULL
        ORDER BY module_no DESC
        ),

        filtered_iv AS (
        SELECT *,
            meas_i[array_length(meas_i, 1)] AS i_last
        FROM selected_iv_test
        WHERE
            module_name IN (SELECT module_name FROM selected_modules)
            AND meas_v IS NOT NULL AND meas_i IS NOT NULL
            AND {temp_condition}
            AND {rel_hum_condition}
            AND (status_desc = 'Completely Encapsulated' OR status_desc = 'Frontside Encapsulated')
            AND array_length(meas_v, 1) = array_length(meas_i, 1)
        ),

        best_per_module AS (
        SELECT DISTINCT ON (filtered_iv.module_name) *
        FROM filtered_iv
        ORDER BY filtered_iv.module_name, i_last ASC
        LIMIT {N_MODULE_SHOW}
        ),

        unnested AS (
        SELECT 
            module_name,
            v,
            i
        FROM best_per_module,
        UNNEST(meas_v, meas_i) AS t(v, i)
        )

        SELECT *
        FROM unnested
        ORDER BY module_name ASC;
        """

        return raw_sql

    def IV_curve_panel_override(self) -> list:
        """Override the default config for IV curve plot.
        """
        override = [
            {
                "matcher": {
                "id": "byName",
                "options": "i"
                },
                "properties": [
                {
                    "id": "custom.axisPlacement",
                    "value": "left"
                },
                {
                    "id": "custom.scaleDistribution",
                    "value": {
                    "log": 10,
                    "type": "log"
                    }
                },
                {
                    "id": "max",
                    "value": 1e-03
                },
                {
                    "id": "min",
                    "value": 1e-09
                },
                {
                    "id": "unit",
                    "value": "sci"
                },
                {
                    "id": "custom.axisLabel",
                    "value": "Leakage Current [A]"
                }
                ]
            },
            {
                "matcher": {
                "id": "byName",
                "options": "v"
                },
                "properties": [
                {
                    "id": "max",
                    "value": 500
                },
                {
                    "id": "min",
                    "value": 0
                },
                {
                    "id": "custom.axisLabel",
                    "value": "Reverse Bias [V]"
                }
                ]
            }
        ]
        
        return override

    def generate_IV_curve_panel_new(self, title: str, raw_sql: str, override: list, gridPos: dict) -> dict:
        """A new version of IV curve panel JSON.
        """
        panel_json = {
        "id": 1,
        "type": "xychart",
        "title": f"{title}",
        "gridPos": gridPos,
        "fieldConfig": {
            "defaults": {
            "custom": {
                "show": "lines",
                "pointSize": {
                "fixed": 5
                },
                "pointShape": "circle",
                "pointStrokeWidth": 1,
                "fillOpacity": 50,
                "axisPlacement": "auto",
                "axisLabel": "",
                "axisColorMode": "text",
                "axisBorderShow": False,
                "scaleDistribution": {
                "type": "linear"
                },
                "axisCenteredZero": False,
                "hideFrom": {
                "tooltip": False,
                "viz": False,
                "legend": False
                }
            },
            "color": {
                "mode": "palette-classic"
            },
            "mappings": [],
            },
            "overrides": override
        },
        "transformations": [
            {
            "id": "partitionByValues",
            "options": {
                "fields": [
                "module_name"
                ],
                "keepFields": False
            }
            }
        ],
        "pluginVersion": "12.0.0",
        "targets": [
            {
            "datasource": {
                "type": "grafana-postgresql-datasource",
                "uid": f"{self.datasource_uid}"
            },
            "editorMode": "code",
            "format": "table",
            "rawQuery": True,
            "rawSql": f"{raw_sql}",
            "refId": "A",
            "sql": {
                "columns": [
                {
                    "parameters": [],
                    "type": "function"
                }
                ],
                "groupBy": [
                {
                    "property": {
                    "type": "string"
                    },
                    "type": "groupBy"
                }
                ],
                "limit": 50
            }
            }
        ],
        "datasource": {
            "type": "grafana-postgresql-datasource",
            "uid": f"{self.datasource_uid}"
        },
        "options": {
            "mapping": "auto",
            "series": [
            {
                "x": {
                "matcher": {
                    "id": "byName",
                    "options": "v"
                }
                },
                "y": {
                "matcher": {
                    "id": "byName",
                    "options": "i"
                }
                }
            }
            ],
            "tooltip": {
            "mode": "single",
            "sort": "none",
            "hideZeros": False
            },
            "legend": {
            "showLegend": True,
            "displayMode": "list",
            "placement": "right",
            "calcs": []
            }
        }
        }

        return panel_json

    # -- Genarate Panels --
    def generate_panels_json(self, dashboard_title: str, config_panels: list) -> list:
        """Build the panel jsons based on the given config file.
        """
        panels = []
        self.assign_gridPos(dashboard_title, config_panels)

        # load information from config file
        for panel in config_panels:
            title = panel["title"]
            chart_type = panel["chart_type"]

            try:
                if chart_type == "text":
                    time = self.get_info(panel, chart_type)     # get limited time range
                    plt_path = self.generate_plot(time)         # generate plot
                    encoded_string = self.convert_png_to_base64(plt_path)   # encode plot to base64
                    content = self.generate_content(encoded_string)         # generate content for text panel
                    panel_json = self.generate_IV_curve_panel(title, content)
                
                elif chart_type == "xychart":
                    filters, temp_condition, rel_hum_condition, gridPos = self.get_info(panel, chart_type)    # get conditions for SQL
                    raw_sql = self.IV_curve_panel_sql(filters, temp_condition, rel_hum_condition)    # generate SQL
                    override = self.IV_curve_panel_override()   # generate override for xy axises
                    panel_json = self.generate_IV_curve_panel_new(title, raw_sql, override, gridPos)

                else:
                    title, table, condition, groupby, filters, gridPos, distinct = self.get_info(panel, chart_type)

                    raw_sql = self.generate_sql(chart_type, table, condition, groupby, filters, distinct)
                    panel_json = self.generate_general_panel(title, raw_sql, table, chart_type, gridPos)

                panels.append(panel_json)

            except Exception as e:
                print(f"[ERROR] Failed to generate panel '{title}' | Reason: {e}")
                print(f"[WARNING] Skip panel: {title}")

        return panels