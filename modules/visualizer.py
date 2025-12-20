import streamlit as st
import pandas as pd
import altair as alt

from modules.database import fetch_table_cached, get_instance_ids_by_names_cached

def render_visualizer(supabase, advertisers=None):
    st.title("📊 Data Explorer")
    st.markdown("Create custom visualizations from your AMC data in seconds.")

    with st.expander("📘 How to use this tool", expanded=False):
        st.markdown("""
        **Welcome!** Follow these simple steps to analyze your data:
        
        1. **Select a Dataset**: Choose the type of data you want to analyze (e.g., 'Ads Report' for performance) from the dropdown below.
        2. **Filter (Optional)**: Use the **Filter Data** section to narrow down results by date, campaign, or specific values.
        3. **Visualize**: The tool automatically creates the best chart for your data. You can customize it in **Chart Settings**.
        4. **Analyze**: Review the **Key Metrics** cards and explore the **Statistics** tab for deeper insights.
        """)

    if not supabase:
        st.error("⚠️ Database connection not available.")
        return

    # --- 1. Data Source Selection ---
    with st.container(border=True):
        st.subheader("1️⃣ Select Data Source")
        col_table, col_advertiser, col_limit = st.columns([2, 2, 1])
        
        tables = {
            "Ads Report (Performance)": "ads_report",
            "Time to Conversion": "amc_time_to_conversion",
            "NTB Gateway ASINs": "amc_ntb_gateway",
            "Media Overlap (Ads vs DSP)": "amc_sponsored_ads_dsp_overlap",
            "Lifestyle Segments": "amc_lifestyle_size"
        }

        descriptions = {
            "Ads Report (Performance)": "General performance metrics (Impressions, Clicks, Spend, Sales) aggregated by date and campaign.",
            "Time to Conversion": "Distribution of the number of days it takes for a user to convert after viewing an ad.",
            "NTB Gateway ASINs": "Identifies which products (ASINs) are most effective at acquiring New-To-Brand customers.",
            "Media Overlap (Ads vs DSP)": "Venn diagram analysis showing unique and shared reach between Sponsored Ads and DSP campaigns.",
            "Lifestyle Segments": "Audience size breakdown by Amazon Lifestyle segments (e.g., 'Tech Enthusiasts', 'Parents')."
        }
        
        with col_table:
            selected_table_label = st.selectbox(
                "Choose a dataset:", 
                list(tables.keys()),
                help="Select the specific AMC report or table you want to analyze."
            )
            table_id = tables[selected_table_label]
            if selected_table_label in descriptions:
                st.caption(f"ℹ️ {descriptions[selected_table_label]}")
            
        with col_advertiser:
            selected_advertiser = st.selectbox(
                "Filter by Advertiser (Optional)", 
                ["🌎 Global"] + (advertisers or []),
                help="Restrict the data to a specific advertiser account."
            )

        with col_limit:
            limit = st.number_input(
                "Max Rows", 
                min_value=100, 
                max_value=50000, 
                value=1000, 
                step=100,
                help="Limit the number of rows fetched to keep the tool fast."
            )

    # Resolve ID
    instance_ids = []
    if selected_advertiser != "🌎 Global":
        ids = get_instance_ids_by_names_cached((selected_advertiser,))
        if ids:
            instance_ids = [int(x) for x in ids]

    # --- 2. Fetch Data ---
    try:
        with st.spinner(f"Fetching data from {selected_table_label}..."):
            df = fetch_table_cached(table_id, int(limit), instance_ids=instance_ids)

        if df is None or df.empty:
            st.warning(
                f"⚠️ No data found in **{selected_table_label}**.\n\n"
                "**Suggestions:**\n"
                "- Try selecting a different Advertiser (or switch to 'Global').\n"
                "- The dataset might be empty for the current selection."
            )
            return
        
        # Pre-processing: Convert date columns
        date_cols = []
        for col in df.columns:
            if "date" in col.lower() or "created_at" in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col])
                    date_cols.append(col)
                except:
                    pass
        
        # --- 2.1 Filter Data (New) ---
        with st.expander("🌪️ Filter Data", expanded=False):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                filter_col = st.selectbox("Filter by Column", ["None"] + list(df.columns))
            
            if filter_col != "None":
                with f_col2:
                    # Determine type
                    if pd.api.types.is_numeric_dtype(df[filter_col]):
                        min_val = float(df[filter_col].min())
                        max_val = float(df[filter_col].max())
                        if min_val < max_val:
                            filter_range = st.slider(f"Range for {filter_col}", min_val, max_val, (min_val, max_val))
                            df = df[(df[filter_col] >= filter_range[0]) & (df[filter_col] <= filter_range[1])]
                        else:
                            st.info(f"Column {filter_col} has constant value: {min_val}")
                    elif pd.api.types.is_datetime64_any_dtype(df[filter_col]):
                        min_date = df[filter_col].min().date()
                        max_date = df[filter_col].max().date()
                        if min_date < max_date:
                            date_range = st.date_input(f"Date Range for {filter_col}", (min_date, max_date))
                            if isinstance(date_range, tuple) and len(date_range) == 2:
                                df = df[(df[filter_col].dt.date >= date_range[0]) & (df[filter_col].dt.date <= date_range[1])]
                        else:
                            st.info(f"Column {filter_col} has constant date: {min_date}")
                    else:
                        # Categorical
                        unique_vals = df[filter_col].unique()
                        if len(unique_vals) < 50: # Limit for multiselect performance
                            selected_vals = st.multiselect(f"Select values for {filter_col}", unique_vals, default=unique_vals)
                            if selected_vals:
                                df = df[df[filter_col].isin(selected_vals)]
                        else:
                            text_val = st.text_input(f"Contains text in {filter_col}")
                            if text_val:
                                df = df[df[filter_col].astype(str).str.contains(text_val, case=False, na=False)]
                
                st.caption(f"Rows after filtering: {len(df)}")

        if df.empty:
            st.warning("Filtered data is empty.")
            return

        # --- Data Summary ---
        st.markdown("### 📈 Data Snapshot")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Rows", len(df))
        m2.metric("Columns", len(df.columns))
        if date_cols:
            min_date = df[date_cols[0]].min().strftime('%Y-%m-%d')
            max_date = df[date_cols[0]].max().strftime('%Y-%m-%d')
            m3.metric("Date Range", f"{min_date} to {max_date}")
        else:
            m3.metric("Date Range", "N/A")

    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    # --- 3. Chart Configuration & Rendering ---
    st.divider()
    
    # Filter columns
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category', 'datetime']).columns.tolist()
    all_cols = df.columns.tolist()

    # --- Smart Defaults Logic ---
    default_x_index = 0
    default_y_index = 0
    default_chart_type_index = 0 # Default to Bar

    # 1. Determine X Axis (Date > Category > Any)
    found_date = False
    for i, col in enumerate(all_cols):
        if col in date_cols:
            default_x_index = i
            found_date = True
            break
    
    if found_date:
        default_chart_type_index = 1 # Line Chart
    else:
        # If no date, try to find a categorical column for Bar chart
        for i, col in enumerate(all_cols):
            if col in categorical_cols and col not in date_cols:
                default_x_index = i
                break

    # 2. Determine Y Axis (Metric)
    priority_metrics = ['spend', 'sales', 'impressions', 'clicks', 'purchases', 'users', 'size', 'count']
    for i, col in enumerate(numeric_cols):
        if any(m in col.lower() for m in priority_metrics):
            default_y_index = i
            break

    # --- KPI Section (New Feature) ---
    if numeric_cols:
        st.markdown("### 📊 Key Metrics Summary")
        kpi_cols = st.columns(min(len(numeric_cols), 4))
        # Filter out ID columns for KPIs
        kpi_candidates = [c for c in numeric_cols if not c.endswith("_id") and "id" not in c]
        
        for i, col in enumerate(kpi_candidates[:4]): # Show max 4 KPIs
            total_val = df[col].sum()
            
            # Format nicely
            if total_val > 1000:
                val_str = f"{total_val:,.0f}"
            else:
                val_str = f"{total_val:.2f}"
                
            with kpi_cols[i]:
                st.metric(label=col.replace("_", " ").title(), value=val_str)
        st.divider()

    # --- Configuration UI (Hidden by default) ---
    st.subheader("2️⃣ Visualization")
    
    with st.expander("⚙️ Configure Chart", expanded=False):
        col_type, col_x, col_y, col_color = st.columns(4)
        
        with col_type:
            chart_type = st.selectbox(
                "Chart Type", 
                ["Bar", "Line", "Area", "Scatter", "Pie", "Donut"],
                index=default_chart_type_index,
                help="Select the type of visualization."
            )
        
        with col_x:
            x_axis = st.selectbox(
                "X Axis (Dimension)", 
                all_cols, 
                index=default_x_index if all_cols else None,
                help="Choose the category or date for the horizontal axis."
            )
        
        with col_y:
            y_axis = st.selectbox(
                "Y Axis (Metric)", 
                numeric_cols, 
                index=default_y_index if numeric_cols else None,
                help="Choose the numeric value to measure."
            )
            
        with col_color:
            color_col = st.selectbox(
                "Color / Group By (Optional)", 
                ["None"] + categorical_cols,
                help="Split the chart by another category."
            )

    if not x_axis or not y_axis:
        st.info("Please select both X and Y axes to generate a chart.")
        return

    # Aggregation Logic
    df_chart = df.copy()
    
    # If color is selected, we group by [X, Color]
    group_cols = [x_axis]
    if color_col != "None":
        group_cols.append(color_col)
        
    # Aggregation Toggle
    if chart_type not in ["Scatter"]:
        if y_axis in numeric_cols:
            df_chart = df_chart.groupby(group_cols, as_index=False)[y_axis].sum()
            agg_text = "SUM"
        else:
            df_chart = df_chart.groupby(group_cols, as_index=False)[y_axis].count()
            agg_text = "COUNT"
        
        st.caption(f"ℹ️ Aggregating data: Showing **{agg_text}** of `{y_axis}` by `{x_axis}`" + (f" and `{color_col}`" if color_col != "None" else ""))

    # --- 4. Render Chart ---
    
    if df_chart.empty:
        st.warning("Resulting data is empty.")
        return

    if not isinstance(df_chart, pd.DataFrame):
        df_chart = pd.DataFrame(df_chart)

    # Base Chart
    base = alt.Chart(df_chart).encode(
        tooltip=group_cols + [y_axis]
    )

    # Color Encoding
    color_encoding = alt.Color(color_col) if color_col != "None" else alt.value("#3182bd") # Default blue

    chart = None

    if chart_type == "Bar":
        chart = base.mark_bar().encode(
            x=alt.X(x_axis, sort='-y' if color_col == "None" else None), # Sort by value if no color group
            y=y_axis,
            color=color_encoding
        )
        
    elif chart_type == "Line":
        chart = base.mark_line(point=True).encode(
            x=x_axis,
            y=y_axis,
            color=color_encoding
        )

    elif chart_type == "Area":
        chart = base.mark_area(opacity=0.6).encode(
            x=x_axis,
            y=y_axis,
            color=color_encoding
        )
        
    elif chart_type == "Scatter":
        chart = base.mark_circle(size=60).encode(
            x=x_axis,
            y=y_axis,
            color=color_encoding
        )
        
    elif chart_type in ["Pie", "Donut"]:
        base = base.encode(theta=alt.Theta(y_axis, stack=True))
        inner_radius = 80 if chart_type == "Donut" else 0
        
        chart = base.mark_arc(outerRadius=120, innerRadius=inner_radius).encode(
            color=alt.Color(x_axis), # Pie charts usually color by the category (X axis)
            order=alt.Order(y_axis, sort='descending'),
            tooltip=[x_axis, y_axis]
        )

    if chart is None:
        st.error("Unsupported chart type.")
        return

    st.altair_chart(chart.interactive(), use_container_width=True)

    # --- 5. Data Export & Preview (New Feature) ---
    st.divider()
    c_action_1, c_action_2 = st.columns([1, 3])
    
    with c_action_1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"{selected_table_label}_export.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with c_action_2:
        with st.expander("🔎 View Raw Data Source"):
            tabs = st.tabs(["📄 Data Table", "🧮 Statistics", "🔗 Correlations"])
            with tabs[0]:
                st.dataframe(df, use_container_width=True)
            with tabs[1]:
                st.dataframe(df.describe(include='all'), use_container_width=True)
            with tabs[2]:
                numeric_df = df.select_dtypes(include=['number'])
                if not numeric_df.empty and len(numeric_df.columns) > 1:
                    st.markdown("Correlation Matrix (1 = Perfect Positive, -1 = Perfect Negative)")
                    st.dataframe(numeric_df.corr().style.background_gradient(cmap="coolwarm"), use_container_width=True)
                else:
                    st.info("Not enough numeric columns to calculate correlations.")
