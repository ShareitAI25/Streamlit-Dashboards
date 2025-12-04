import pandas as pd
import random
import datetime
from google.genai import types

# Default system instruction
DEFAULT_SYSTEM_INSTRUCTION = "You are an expert Amazon Marketing Cloud (AMC) Analyst. You help users optimize campaigns, analyze ROAS, and identify New-To-Brand opportunities. Keep answers concise and professional."

def get_agent_response(client, system_instruction, user_query, selected_advertisers, date_range=None):
    """
    Generates response using Gemini API for text and Mock Logic for data/charts.
    Returns a dict with: text, sql, data (DataFrame), chart_config (dict)
    """
    # 1. Determine Context
    if not selected_advertisers:
        where_clause = ""
        context_msg = "Global Context"
    else:
        adv_list = ", ".join([f"'{adv}'" for adv in selected_advertisers])
        where_clause = f"WHERE advertiser_name IN ({adv_list})"
        context_msg = f"Filtered Context: {selected_advertisers}"

    # Date Range Context
    date_msg = "Last 30 Days"
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        where_clause += f"\n    AND date BETWEEN '{start_date}' AND '{end_date}'"
        date_msg = f"{start_date} to {end_date}"

    # 2. Call Gemini API (Step A)
    ai_text = ""
    try:
        if client:
            # Append context to the query for better AI awareness
            full_prompt = f"{user_query}\n\n[Context: User is analyzing data for {context_msg} during {date_msg}.]"
            
            # Use the passed system_instruction or fallback to default
            instruction = system_instruction if system_instruction else DEFAULT_SYSTEM_INSTRUCTION
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(system_instruction=instruction),
                contents=full_prompt
            )
            ai_text = response.text
        else:
            ai_text = "⚠️ Gemini API Key not found or client not initialized. Please check your secrets."
    except Exception as e:
        ai_text = f"⚠️ Error connecting to Gemini API: {str(e)}. Using fallback response."

    # 3. Hybrid Logic: Mock Data Generation (Step B)
    query_lower = user_query.lower()
    sql_query = None
    df = None
    chart_config = None
    
    # --- SCENARIO 1: CAMPAIGN AUDIT ---
    if any(k in query_lower for k in ["audit", "wasted", "efficiency"]):
        sql_query = f"""
        SELECT campaign_name, spend, impressions, roas, status
        FROM campaign_audit
        {where_clause}
        AND roas = 0
        ORDER BY spend DESC
        LIMIT 5;
        """
        
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
    elif any(k in query_lower for k in ["time", "conversion", "days"]):
        sql_query = f"""
        SELECT days_to_convert, count(*) as conversion_count
        FROM conversion_time_distribution
        {where_clause}
        GROUP BY days_to_convert
        ORDER BY days_to_convert ASC;
        """
        
        data_rows = []
        for i in range(1, 15):
            count = int(1000 * (1 / i)) # Decay
            data_rows.append({
                "Days_to_Convert": i,
                "Conversion_Count": count
            })
        df = pd.DataFrame(data_rows)
        chart_config = {"type": "bar", "x": "Days_to_Convert", "y": "Conversion_Count"}

    # --- SCENARIO 3: PRODUCT STRATEGY / GATEWAY ASINS ---
    elif any(k in query_lower for k in ["product", "asin", "strategy"]):
        sql_query = f"""
        SELECT asin, product_name, ntb_orders, total_sales
        FROM gateway_asins
        {where_clause}
        ORDER BY ntb_orders DESC
        LIMIT 5;
        """
        
        data_rows = []
        for i in range(5):
            data_rows.append({
                "ASIN": f"B00{random.randint(10000,99999)}",
                "Product Name": f"Product {i+1}",
                "NTB_Orders": random.randint(50, 500),
                "Total_Sales": round(random.uniform(5000, 20000), 2)
            })
        df = pd.DataFrame(data_rows)
        chart_config = {"type": "bar", "x": "ASIN", "y": "NTB_Orders"}

    # --- SCENARIO 4: DASHBOARD / PERFORMANCE (Explicit Request) ---
    elif any(k in query_lower for k in ["dashboard", "sales", "overview", "performance", "chart", "graph"]):
        sql_query = f"""
        SELECT 
            date, 
            campaign_name, 
            SUM(spend) as total_spend, 
            SUM(impressions) as total_impressions
        FROM amc_consolidated
        {where_clause}
        GROUP BY date, campaign_name
        ORDER BY date DESC
        LIMIT 100;
        """
        
        dates = pd.date_range(end=datetime.date.today(), periods=10).tolist()
        campaigns = [f"Campaign_{i}" for i in range(1, 6)]
        data_rows = []
        for _ in range(20):
            data_rows.append({
                "date": random.choice(dates),
                "campaign": random.choice(campaigns),
                "spend": round(random.uniform(100, 5000), 2),
                "impressions": random.randint(1000, 50000)
            })
        df = pd.DataFrame(data_rows).sort_values("date")
        chart_config = {"type": "line", "x": "date", "y": "spend"}

    return {
        "text": ai_text,
        "sql": sql_query,
        "data": df,
        "chart_config": chart_config
    }
