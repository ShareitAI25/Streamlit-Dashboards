from fpdf import FPDF

def generate_pdf_report(user_query, insight_text, df):
    """
    Generates a PDF report using FPDF.
    Returns the PDF content as bytes.
    """
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "AMC Insights Service", ln=True, align="C")
    pdf.ln(10)
    
    # Title (User Query)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Query: {user_query}", ln=True)
    pdf.ln(5)
    
    # Executive Summary
    pdf.set_font("Arial", "", 11)
    # Multi_cell for text wrapping
    # Encode to latin-1 to handle some special chars, though basic FPDF has limits
    safe_text = insight_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 7, f"Executive Summary:\n{safe_text}")
    pdf.ln(10)
    
    # Data Table
    if df is not None and not df.empty:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 10, "Data Preview:", ln=True)
        
        # Table Header
        pdf.set_font("Arial", "B", 9)
        cols = df.columns.tolist()
        if cols:
            col_width = 190 / len(cols) # Distribute width roughly
            
            for col in cols:
                pdf.cell(col_width, 8, str(col), border=1)
            pdf.ln()
            
            # Table Rows
            pdf.set_font("Arial", "", 9)
            for index, row in df.head(20).iterrows(): # Limit to 20 rows for the PDF preview
                for col in cols:
                    val = str(row[col])
                    # Truncate if too long
                    if len(val) > 20:
                        val = val[:17] + "..."
                    pdf.cell(col_width, 8, val, border=1)
                pdf.ln()
        
    # Return bytes
    return pdf.output(dest='S').encode('latin-1')
