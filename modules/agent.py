import pandas as pd
import random
import datetime
import json
import re
from google.genai import types

from modules.database import get_company_marketplace_ids_for_instance_ids_cached

# Default system instruction
DEFAULT_SYSTEM_INSTRUCTION = """You are an expert Amazon Marketing Cloud (AMC) Analyst. 
You have access to a Supabase database with the following schema:

-- AMC Tables
1. amc_campaign (campaign_id, name)
2. amc_chat_history (id, session_id, role, content, sql_query, chart_config, data_snapshot, created_at)
4. amc_instance (amc_instance_id, company_id, region_id, name, created_at, instance_id)
5. amc_lifestyle (amc_lifestyle_id, name)
6. amc_lifestyle_size (amc_lifestyle_size_id, amc_query_execution_id, size, amc_lifestyle_id)
7. amc_ntb_gateway (amc_ntb_gateaway_api, amc_query_execution_id, users_with_purchase, ntb_users, asin, gateway_asin_rank)
8. amc_query_execution (amc_query_execution_id, created_at, amc_instance_id, start_date, end_date)
9. amc_query_execution_company_marketplace (amc_query_execution_company_id, amc_query_execution_id, company_marketplace_id)
10. amc_sponsored_ads_dsp_overlap (id, amc_query_execution_id, exposure_group, users_that_purchased, unique_reach, total_purchases, total_product_sales)
11. amc_time_to_conversion (id, amc_query_execution_id, campaign_id, time_to_conversion_bucket, purchases, total_brand_purchases)

-- Other Related Tables
12. ads_report (report_id, company_marketplace_id, start_date, end_date, weekly, asin, clicks, spend, sales, purchases, impressions)
13. company (company_id, created_at, name)
14. company_marketplace (company_marketplace_id, company_id, marketplace_id)
15. marketplace (marketplace_id, country_code, currency_id, region_id, country_name)
16. region (region_id, endpoint_code, aws_region, name)

If the user asks for information that requires querying these tables, and it is NOT one of the standard commands, 
you must output a JSON object to execute the query dynamically.

The JSON format must be:
{
  "response_text": "Brief explanation of what you are showing.",
  "query": {
    "table": "table_name",
    "select": "col1, col2",
    "order_by": "col_name",
    "order_direction": "desc",
    "limit": 10,
    "filters": [
        {"column": "col_name", "operator": "eq", "value": "value"}
    ]
  },
  "chart_config": {"type": "bar", "x": "col1", "y": "col2"}
}

IMPORTANT:
1. 'query' MUST be an object, NOT a string.
2. 'filters' MUST be a list of objects.
3. For foreign keys, use PostgREST syntax in 'select'. Example: "size, amc_lifestyle(name)".
4. Supported operators: eq, gt, lt, gte, lte, like, ilike, in.
5. NEVER hallucinate tables. ONLY use the tables listed above.
6. If the user asks for "lifestyles", query 'amc_lifestyle_size' joined with 'amc_lifestyle'.
7. If the user explicitly asks for a table view, set "chart_config" to null.
8. Do NOT return SQL strings. You must return the 'query' object for the Supabase client.

EXAMPLES:

User: "Show me the top 10 lifestyles"
JSON:
{
  "response_text": "Here are the top 10 lifestyle segments by size.",
  "query": {
    "table": "amc_lifestyle_size",
    "select": "size, amc_lifestyle(name)",
    "order_by": "size",
    "order_direction": "desc",
    "limit": 10,
    "filters": []
  },
  "chart_config": {"type": "bar", "x": "amc_lifestyle.name", "y": "size"}
}

User: "Show me the top 10 lifestyles as a table"
JSON:
{
  "response_text": "Here are the top 10 lifestyle segments.",
  "query": {
    "table": "amc_lifestyle_size",
    "select": "size, amc_lifestyle(name)",
    "order_by": "size",
    "order_direction": "desc",
    "limit": 10,
    "filters": []
  },
  "chart_config": null
}

User: "List all advertisers"
JSON:
{
  "response_text": "Here is the list of advertisers.",
  "query": {
    "table": "amc_instance",
    "select": "name, region_id",
    "order_by": "name",
    "order_direction": "asc",
    "limit": 50,
    "filters": []
  },
  "chart_config": null
}

If no data is needed, set "query" to null.
Do NOT output markdown code blocks for the JSON. Output raw JSON.
Keep answers concise and professional."""

def get_agent_response(
    client,
    supabase_client,
    system_instruction,
    user_query,
    selected_advertisers,
    date_range=None,
    chat_history=None,
    selected_instance_ids=None,
):
    """
    Generates response using Gemini API for text and Mock Logic for data/charts.
    Returns a dict with: text, sql, data (DataFrame), chart_config (dict)
    """
    # --- SPECIAL COMMAND: SUPABASE TEST ---
    if user_query.lower().strip() == "supabase":
        try:
            if supabase_client:
                response = supabase_client.table("company").select("*").execute()
                data = response.data
                if data:
                    df = pd.DataFrame(data)
                    return {
                        "text": "✅ Connection Successful! Here is the data from the `company` table in Supabase:",
                        "sql": "SELECT * FROM company;",
                        "data": df,
                        "chart_config": None
                    }
                else:
                    return {
                        "text": "⚠️ Connection Successful, but the `company` table is empty.",
                        "sql": "SELECT * FROM company;",
                        "data": None,
                        "chart_config": None
                    }
            else:
                return {
                    "text": "⚠️ Supabase client is not initialized. Please check your secrets.",
                    "sql": None,
                    "data": None,
                    "chart_config": None
                }
        except Exception as e:
            return {
                "text": f"⚠️ Error querying Supabase: {str(e)}",
                "sql": None,
                "data": None,
                "chart_config": None
            }

    # 1. Determine Context
    selected_instance_ids = selected_instance_ids or []
    if not selected_advertisers:
        context_msg = "Global Context"
    else:
        context_msg = f"Filtered Context: {selected_advertisers}"

    # Date Range Context
    date_msg = "Last 30 Days"
    start_date_str = None
    end_date_str = None

    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        date_msg = f"{start_date} to {end_date}"

    def _sql_instance_filter(alias_q: str = "q"):
        if not selected_instance_ids:
            return ""
        ids_csv = ", ".join(str(i) for i in selected_instance_ids)
        return f"AND {alias_q}.amc_instance_id IN ({ids_csv})"

    def _sql_execution_window_overlap(alias_q: str = "q"):
        if not (start_date_str and end_date_str):
            return ""
        return (
            f"AND {alias_q}.start_date <= '{end_date_str}' "
            f"AND {alias_q}.end_date >= '{start_date_str}'"
        )

    # 2. Command vs Prompt Logic
    query_lower = user_query.lower()
    sql_query = None
    df = None
    chart_config = None
    ai_text = ""
    is_command = False

    # --- SCENARIO 1: CAMPAIGN AUDIT ---
    if any(k in query_lower for k in ["audit", "wasted", "efficiency"]):
        is_command = True
        ai_text = "### 🛡️ Campaign Audit\nAnalyzing inefficient campaigns with zero ROAS..."
        sql_query = (
            "-- NOTE: `campaign_audit` no está disponible en el esquema actual.\n"
            "-- Para este insight se necesitaría una tabla/vista con ROAS por campaña."
        )
        
        data_rows = []
        for i in range(5):
            data_rows.append({
                "Campaign Name": f"Inefficient_Camp_{i+1}",
                "Spend": round(random.uniform(1000, 5000), 2),
                "Impressions": random.randint(10000, 50000),
                "ROAS": 0.0,
                "Status": "Inefficient"
            })
        df = pd.DataFrame(data_rows)
        chart_config = {"type": "bar", "x": "Campaign Name", "y": "Spend"}

    # --- SCENARIO 2: TIME-TO-CONVERSION ---
    elif any(k in query_lower for k in ["time to conversion", "conversion days", "conversion time"]):
        is_command = True
        ai_text = "### ⏱️ Time to Conversion Analysis\nHere is the distribution of days taken for users to convert:"
        sql_query = f"""
SELECT t.time_to_conversion_bucket, SUM(t.purchases) AS total_purchases
FROM amc_time_to_conversion t
JOIN amc_query_execution q
    ON t.amc_query_execution_id = q.amc_query_execution_id
WHERE 1=1
    {_sql_instance_filter('q')}
    {_sql_execution_window_overlap('q')}
GROUP BY t.time_to_conversion_bucket
ORDER BY total_purchases DESC;
"""
        
        try:
            if supabase_client:
                query = supabase_client.table("amc_time_to_conversion").select(
                    "time_to_conversion_bucket, purchases, amc_query_execution!inner(amc_instance_id, start_date, end_date)"
                )

                if selected_instance_ids:
                    query = query.in_("amc_query_execution.amc_instance_id", selected_instance_ids)
                
                if start_date_str and end_date_str:
                    query = query.lte("amc_query_execution.start_date", end_date_str).gte("amc_query_execution.end_date", start_date_str)
                
                response = query.execute()
                if response.data:
                    df = pd.DataFrame(response.data)
                    # Aggregate if needed, assuming raw data might be granular
                    df = df.groupby("time_to_conversion_bucket", as_index=False)["purchases"].sum()
                    chart_config = {"type": "bar", "x": "time_to_conversion_bucket", "y": "purchases"}
                else:
                    df = pd.DataFrame() # Empty
            else:
                 # Fallback Mock
                data_rows = []
                for i in range(1, 15):
                    count = int(1000 * (1 / i)) # Decay
                    data_rows.append({
                        "time_to_conversion_bucket": f"{i} days",
                        "purchases": count
                    })
                df = pd.DataFrame(data_rows)
                chart_config = {"type": "bar", "x": "time_to_conversion_bucket", "y": "purchases"}
        except Exception as e:
             print(f"Error fetching Time to Conversion: {e}")
             df = pd.DataFrame()

    # --- SCENARIO 3: NEW-TO-BRAND (NTB) METRICS ---
    elif any(k in query_lower for k in ["ntb metrics", "new to brand metrics", "ntb analysis"]):
        is_command = True
        ai_text = "### 🆕 New-To-Brand (NTB) Analysis\nTop Gateway ASINs driving new customer acquisition (Source: NTB Gateway):"
        sql_query = f"""
SELECT g.asin, g.ntb_users, g.users_with_purchase
FROM amc_ntb_gateway g
JOIN amc_query_execution q
    ON g.amc_query_execution_id = q.amc_query_execution_id
WHERE 1=1
    {_sql_instance_filter('q')}
    {_sql_execution_window_overlap('q')}
ORDER BY g.ntb_users DESC
LIMIT 10;
"""
        
        try:
            if supabase_client:
                query = supabase_client.table("amc_ntb_gateway").select(
                    "asin, ntb_users, users_with_purchase, amc_query_execution!inner(amc_instance_id, start_date, end_date)"
                )

                if selected_instance_ids:
                    query = query.in_("amc_query_execution.amc_instance_id", selected_instance_ids)
                
                if start_date_str and end_date_str:
                    query = query.lte("amc_query_execution.start_date", end_date_str).gte("amc_query_execution.end_date", start_date_str)
                
                response = query.order("ntb_users", desc=True).limit(10).execute()
                if response.data:
                    df = pd.DataFrame(response.data)
                    chart_config = {"type": "bar", "x": "asin", "y": "ntb_users"}
                else:
                    df = pd.DataFrame()
            else:
                # Fallback Mock
                data_rows = []
                for i in range(5):
                    data_rows.append({
                        "asin": f"B00{random.randint(10000,99999)}",
                        "ntb_users": random.randint(50, 500),
                        "users_with_purchase": random.randint(100, 1000)
                    })
                df = pd.DataFrame(data_rows)
                chart_config = {"type": "bar", "x": "asin", "y": "ntb_users"}
        except Exception as e:
            print(f"Error fetching NTB Metrics: {e}")
            df = pd.DataFrame()

    # --- SCENARIO 4: CROSS-PURCHASE ANALYSIS ---
    # REMOVED: Table amc_asin_cross_purchase no longer exists in schema.
    # elif any(k in query_lower for k in ["cross purchase", "cross-purchase", "asin overlap"]):
    #     ...

    # --- SCENARIO 6: QUERY EXECUTION LOG ---
    elif any(k in query_lower for k in ["query execution log", "system status check", "check system status"]):
        is_command = True
        ai_text = "### 📜 Query Execution Log\nRecent system activity and query status:"
        sql_query = f"""
SELECT q.created_at, i.name AS instance_name
FROM amc_query_execution q
JOIN amc_instance i ON q.amc_instance_id = i.amc_instance_id
WHERE 1=1
    {_sql_instance_filter('q')}
    {_sql_execution_window_overlap('q')}
ORDER BY q.created_at DESC
LIMIT 20;
"""
        
        try:
            if supabase_client:
                # Using PostgREST syntax for join: select("col, relation(col)")
                query = supabase_client.table("amc_query_execution").select("created_at, amc_instance(name)")

                if selected_instance_ids:
                    query = query.in_("amc_instance_id", selected_instance_ids)

                if start_date_str and end_date_str:
                    query = query.lte("start_date", end_date_str).gte("end_date", start_date_str)

                response = query.order("created_at", desc=True).limit(20).execute()
                if response.data:
                    # Flatten the response because nested dicts don't display well in simple dataframes
                    flat_data = []
                    for item in response.data:
                        inst_name = "Unknown"
                        if item.get("amc_instance"):
                            inst_name = item["amc_instance"].get("name", "Unknown")
                        
                        flat_data.append({
                            "created_at": item.get("created_at"),
                            "instance_name": inst_name
                        })
                    df = pd.DataFrame(flat_data)
                    chart_config = None # Table only
                else:
                    df = pd.DataFrame()
            else:
                # Fallback Mock
                data_rows = []
                for i in range(10):
                    data_rows.append({
                        "created_at": (datetime.date.today() - datetime.timedelta(days=i)).isoformat(),
                        "instance_name": f"Instance_{random.randint(1,5)}"
                    })
                df = pd.DataFrame(data_rows)
                chart_config = None
        except Exception as e:
            print(f"Error fetching Query Executions: {e}")
            df = pd.DataFrame()

    # --- SCENARIO 7: ADVERTISERS LIST ---
    elif any(k in query_lower for k in ["list advertisers", "show instances", "list companies"]):
        is_command = True
        ai_text = "### 🏢 Registered Advertisers\nList of all AMC instances connected to this account:"
        sql_query = """
        SELECT amc_instance_id, name, instance_id, region_id
        FROM amc_instance
        ORDER BY name ASC;
        """
        
        try:
            if supabase_client:
                response = supabase_client.table("amc_instance").select("amc_instance_id, name, instance_id, region_id").order("name").execute()
                if response.data:
                    df = pd.DataFrame(response.data)
                    chart_config = None
                else:
                    df = pd.DataFrame()
            else:
                # Fallback Mock
                data_rows = []
                for i in range(5):
                    data_rows.append({
                        "amc_instance_id": i+1,
                        "name": f"Advertiser {i+1}",
                        "instance_id": f"amc_{random.randint(1000,9999)}",
                        "region_id": 1
                    })
                df = pd.DataFrame(data_rows)
                chart_config = None
        except Exception as e:
            print(f"Error fetching Advertisers: {e}")
            df = pd.DataFrame()

    # --- SCENARIO 8: SPEND TREND ---
    elif any(k in query_lower for k in ["spend trend", "spend history", "cost evolution"]):
        is_command = True
        ai_text = "### 📈 Spend Trend Analysis\nDaily spend evolution (Source: Ads Report):"
        sql_query = f"""
WITH execs AS (
    SELECT q.amc_query_execution_id
    FROM amc_query_execution q
    WHERE 1=1
        {_sql_instance_filter('q')}
        {_sql_execution_window_overlap('q')}
), cm AS (
    SELECT DISTINCT qcm.company_marketplace_id
    FROM amc_query_execution_company_marketplace qcm
    JOIN execs e ON e.amc_query_execution_id = qcm.amc_query_execution_id
)
SELECT r.start_date, SUM(r.spend) AS total_spend
FROM ads_report r
JOIN cm ON cm.company_marketplace_id = r.company_marketplace_id
WHERE 1=1
    {f"AND r.start_date <= '{end_date_str}' AND r.end_date >= '{start_date_str}'" if (start_date_str and end_date_str) else ""}
GROUP BY r.start_date
ORDER BY r.start_date ASC;
"""
        
        try:
            if supabase_client:
                # Fetching raw data and aggregating in Pandas. Limit to avoid overload.
                query = supabase_client.table("ads_report").select("start_date, spend")

                if selected_instance_ids:
                    cm_ids = get_company_marketplace_ids_for_instance_ids_cached(
                        tuple(int(i) for i in selected_instance_ids),
                        start_date_str,
                        end_date_str,
                    )
                    if cm_ids:
                        query = query.in_("company_marketplace_id", cm_ids)
                    else:
                        df = pd.DataFrame()
                        chart_config = None
                        raise RuntimeError("No company_marketplace_id found for selected instance(s).")
                
                if start_date_str and end_date_str:
                     query = query.lte("start_date", end_date_str).gte("end_date", start_date_str)
                
                response = query.order("start_date", desc=True).limit(2000).execute()
                if response.data:
                    df = pd.DataFrame(response.data)
                    df = df.groupby("start_date", as_index=False)["spend"].sum()
                    df.rename(columns={"spend": "total_spend", "start_date": "date"}, inplace=True)
                    df.sort_values("date", inplace=True)
                    chart_config = {"type": "line", "x": "date", "y": "total_spend"}
                else:
                    df = pd.DataFrame()
            else:
                df = pd.DataFrame()
                chart_config = None
        except Exception as e:
            print(f"Error fetching Spend Trend: {e}")
            df = pd.DataFrame()

    # --- SCENARIO 9: DASHBOARD / PERFORMANCE (Explicit Request) ---
    elif any(k in query_lower for k in ["performance dashboard", "sales overview", "main dashboard"]):
        is_command = True
        ai_text = "### 📊 Performance Dashboard\nOverview of Top ASINs by Sales (Source: Ads Report):"
        sql_query = f"""
WITH execs AS (
    SELECT q.amc_query_execution_id
    FROM amc_query_execution q
    WHERE 1=1
        {_sql_instance_filter('q')}
        {_sql_execution_window_overlap('q')}
), cm AS (
    SELECT DISTINCT qcm.company_marketplace_id
    FROM amc_query_execution_company_marketplace qcm
    JOIN execs e ON e.amc_query_execution_id = qcm.amc_query_execution_id
)
SELECT r.asin,
             SUM(r.spend) AS total_spend,
             SUM(r.sales) AS total_sales,
             SUM(r.impressions) AS total_impressions
FROM ads_report r
JOIN cm ON cm.company_marketplace_id = r.company_marketplace_id
WHERE 1=1
    {f"AND r.start_date <= '{end_date_str}' AND r.end_date >= '{start_date_str}'" if (start_date_str and end_date_str) else ""}
GROUP BY r.asin
ORDER BY total_sales DESC
LIMIT 20;
"""
        
        try:
            if supabase_client:
                query = supabase_client.table("ads_report").select("asin, spend, sales, impressions")

                if selected_instance_ids:
                    cm_ids = get_company_marketplace_ids_for_instance_ids_cached(
                        tuple(int(i) for i in selected_instance_ids),
                        start_date_str,
                        end_date_str,
                    )
                    if cm_ids:
                        query = query.in_("company_marketplace_id", cm_ids)
                    else:
                        df = pd.DataFrame()
                        chart_config = None
                        raise RuntimeError("No company_marketplace_id found for selected instance(s).")
                
                if start_date_str and end_date_str:
                     query = query.lte("start_date", end_date_str).gte("end_date", start_date_str)
                
                response = query.limit(2000).execute()
                if response.data:
                    df = pd.DataFrame(response.data)
                    df = df.groupby("asin", as_index=False)[["spend", "sales", "impressions"]].sum()
                    df.sort_values("sales", ascending=False, inplace=True)
                    df = df.head(20)
                    chart_config = {"type": "bar", "x": "asin", "y": "sales"}
                else:
                    df = pd.DataFrame()
            else:
                df = pd.DataFrame()
                chart_config = None
        except Exception as e:
            print(f"Error fetching Dashboard: {e}")
            df = pd.DataFrame()

    # --- SCENARIO 12: OVERLAP ANALYSIS (New) ---
    elif any(k in query_lower for k in ["overlap", "dsp", "exposure group"]):
        is_command = True
        ai_text = "### 🔀 Media Overlap Analysis\nImpact of different ad exposure groups (Sponsored Ads vs DSP):"
        sql_query = f"""
SELECT o.exposure_group,
             o.unique_reach,
             o.users_that_purchased,
             o.total_product_sales
FROM amc_sponsored_ads_dsp_overlap o
JOIN amc_query_execution q
    ON o.amc_query_execution_id = q.amc_query_execution_id
WHERE 1=1
    {_sql_instance_filter('q')}
    {_sql_execution_window_overlap('q')}
ORDER BY o.unique_reach DESC;
"""
        
        try:
            if supabase_client:
                query = supabase_client.table("amc_sponsored_ads_dsp_overlap").select(
                    "exposure_group, unique_reach, users_that_purchased, total_product_sales, amc_query_execution!inner(amc_instance_id, start_date, end_date)"
                )

                if selected_instance_ids:
                    query = query.in_("amc_query_execution.amc_instance_id", selected_instance_ids)
                
                if start_date_str and end_date_str:
                    query = query.lte("amc_query_execution.start_date", end_date_str).gte("amc_query_execution.end_date", start_date_str)
                
                response = query.order("unique_reach", desc=True).execute()
                if response.data:
                    df = pd.DataFrame(response.data)
                    chart_config = {"type": "bar", "x": "exposure_group", "y": "unique_reach"}
                else:
                    df = pd.DataFrame()
            else:
                df = pd.DataFrame()
                chart_config = None
        except Exception as e:
            print(f"Error fetching Overlap: {e}")
            df = pd.DataFrame()

    # --- SCENARIO 10: GATEWAY ASINS (New Table) ---
    elif any(k in query_lower for k in ["gateway asins", "entry products", "first purchase analysis"]):
        is_command = True
        ai_text = "### 🚪 Gateway ASINs\nProducts that most frequently drive new-to-brand customers:"
        sql_query = f"""
SELECT g.asin, g.ntb_users, g.users_with_purchase
FROM amc_ntb_gateway g
JOIN amc_query_execution q
    ON g.amc_query_execution_id = q.amc_query_execution_id
WHERE 1=1
    {_sql_instance_filter('q')}
    {_sql_execution_window_overlap('q')}
ORDER BY g.ntb_users DESC
LIMIT 10;
"""
        
        try:
            if supabase_client:
                query = supabase_client.table("amc_ntb_gateway").select(
                    "asin, ntb_users, users_with_purchase, amc_query_execution!inner(amc_instance_id, start_date, end_date)"
                )

                if selected_instance_ids:
                    query = query.in_("amc_query_execution.amc_instance_id", selected_instance_ids)
                
                if start_date_str and end_date_str:
                    query = query.lte("amc_query_execution.start_date", end_date_str).gte("amc_query_execution.end_date", start_date_str)
                
                response = query.order("ntb_users", desc=True).limit(10).execute()
                if response.data:
                    df = pd.DataFrame(response.data)
                    chart_config = {"type": "bar", "x": "asin", "y": "ntb_users"}
                else:
                    df = pd.DataFrame()
            else:
                df = pd.DataFrame()
                chart_config = None
        except Exception as e:
            print(f"Error fetching Gateway ASINs: {e}")
            df = pd.DataFrame()

    # --- SCENARIO 11: LIFESTYLE SEGMENTS (New Table) ---
    elif any(k in query_lower for k in ["lifestyle segments", "lifestyle analysis", "demographic segments"]):
        is_command = True
        ai_text = "### 🧘 Lifestyle Segments\nSize of different lifestyle audiences:"
        sql_query = f"""
SELECT l.name,
             s.size
FROM amc_lifestyle_size s
JOIN amc_lifestyle l
    ON s.amc_lifestyle_id = l.amc_lifestyle_id
JOIN amc_query_execution q
    ON s.amc_query_execution_id = q.amc_query_execution_id
WHERE 1=1
    {_sql_instance_filter('q')}
    {_sql_execution_window_overlap('q')}
ORDER BY s.size DESC;
"""
        
        try:
            if supabase_client:
                query = supabase_client.table("amc_lifestyle_size").select(
                    "size, amc_lifestyle(name), amc_query_execution!inner(amc_instance_id, start_date, end_date)"
                )

                if selected_instance_ids:
                    query = query.in_("amc_query_execution.amc_instance_id", selected_instance_ids)
                
                if start_date_str and end_date_str:
                    query = query.lte("amc_query_execution.start_date", end_date_str).gte("amc_query_execution.end_date", start_date_str)
                
                response = query.order("size", desc=True).execute()
                if response.data:
                    flat_data = []
                    for item in response.data:
                        l_name = "Unknown"
                        if item.get("amc_lifestyle"):
                            l_name = item["amc_lifestyle"].get("name", "Unknown")
                        flat_data.append({"segment": l_name, "size": item.get("size")})
                    
                    df = pd.DataFrame(flat_data)
                    chart_config = {"type": "bar", "x": "segment", "y": "size"}
                else:
                    df = pd.DataFrame()
            else:
                df = pd.DataFrame()
                chart_config = None
        except Exception as e:
            print(f"Error fetching Lifestyle Segments: {e}")
            df = pd.DataFrame()

    # 3. Fallback to Gemini (Prompt Mode with Dynamic Query)
    if not is_command:
        try:
            if client:
                # Build History Context
                history_text = ""
                if chat_history:
                    history_text = "\n[Chat History]:\n"
                    for msg in chat_history[-5:]:
                        role = msg.get("role", "unknown")
                        content = msg.get("content", "")
                        history_text += f"{role.upper()}: {content}\n"
                        if role == "assistant" and msg.get("data") is not None:
                            try:
                                if isinstance(msg["data"], pd.DataFrame):
                                    data_preview = msg["data"].head(5).to_string(index=False)
                                    history_text += f"[System Data Context]: The user saw this data:\n{data_preview}\n"
                            except Exception:
                                pass

                full_prompt = f"{history_text}\nUSER QUERY: {user_query}\n\n[Context: User is analyzing data for {context_msg} during {date_msg}.]"
                
                instruction = system_instruction if system_instruction else DEFAULT_SYSTEM_INSTRUCTION
                
                # Request JSON response
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    config=types.GenerateContentConfig(
                        system_instruction=instruction,
                        response_mime_type="application/json" 
                    ),
                    contents=full_prompt
                )
                
                raw_response = response.text
                
                # Parse JSON
                try:
                    # Clean up markdown code blocks if present (despite instructions)
                    clean_json = raw_response.strip()
                    if clean_json.startswith("```json"):
                        clean_json = clean_json[7:]
                    if clean_json.endswith("```"):
                        clean_json = clean_json[:-3]
                    
                    response_json = json.loads(clean_json)
                    
                    if not isinstance(response_json, dict):
                        # Handle case where JSON is a list or primitive
                        ai_text = str(response_json)
                        query_obj = None
                        chart_config = None
                    else:
                        ai_text = response_json.get("response_text", "")
                        query_obj = response_json.get("query")
                        chart_config = response_json.get("chart_config")
                    
                    # Execute Dynamic Query
                    if query_obj and isinstance(query_obj, dict) and supabase_client:
                        try:
                            table = query_obj.get("table")
                            select = query_obj.get("select", "*")
                            order_by = query_obj.get("order_by")
                            order_dir = query_obj.get("order_direction", "desc")
                            limit = query_obj.get("limit", 10)
                            filters = query_obj.get("filters", [])
                            
                            q = supabase_client.table(table).select(select)
                            
                            if isinstance(filters, list):
                                for f in filters:
                                    if isinstance(f, dict):
                                        col = f.get("column")
                                        op = f.get("operator")
                                        val = f.get("value")
                                        
                                        if col and op:
                                            if op == "eq": q = q.eq(col, val)
                                            elif op == "gt": q = q.gt(col, val)
                                            elif op == "lt": q = q.lt(col, val)
                                            elif op == "gte": q = q.gte(col, val)
                                            elif op == "lte": q = q.lte(col, val)
                                            elif op == "like": q = q.like(col, val)
                                            elif op == "ilike": q = q.ilike(col, val)
                                            elif op == "in": q = q.in_(col, val)
                                
                            if order_by:
                                q = q.order(order_by, desc=(order_dir == "desc"))
                            
                            if limit:
                                q = q.limit(limit)
                                
                            res = q.execute()
                            if res.data:
                                # Flatten nested JSON responses (e.g. amc_lifestyle: {name: ...})
                                flat_data = []
                                for item in res.data:
                                    flat_item = {}
                                    for k, v in item.items():
                                        if isinstance(v, dict):
                                            for sub_k, sub_v in v.items():
                                                flat_item[f"{k}.{sub_k}"] = sub_v
                                        else:
                                            flat_item[k] = v
                                    flat_data.append(flat_item)
                                
                                df = pd.DataFrame(flat_data)
                                sql_query = f"-- Dynamic Query Generated by Gemini\n-- Table: {table}\n-- Filters: {filters}"
                            else:
                                df = pd.DataFrame()
                                
                        except Exception as e:
                            ai_text += f"\n\n⚠️ Error executing dynamic query: {str(e)}"
                            df = pd.DataFrame()
                    
                except json.JSONDecodeError:
                    # Fallback if JSON parsing fails (model returned text)
                    ai_text = raw_response
                    
            else:
                ai_text = "⚠️ Gemini API Key not found or client not initialized. Please check your secrets."
        except Exception as e:
            ai_text = f"⚠️ Error connecting to Gemini API: {str(e)}. Using fallback response."

    return {
        "text": ai_text,
        "sql": sql_query,
        "data": df,
        "chart_config": chart_config
    }

def get_advertisers(supabase_client):
    """Fetch distinct advertiser names from Supabase."""
    try:
        if supabase_client:
            response = supabase_client.table("amc_instance").select("name").execute()
            data = response.data
            advertisers = [item["name"] for item in data if "name" in item]
            return advertisers
    except Exception as e:
        print(f"Error fetching advertisers from Supabase: {e}")
    return []