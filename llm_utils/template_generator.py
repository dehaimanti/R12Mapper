import io
import xlsxwriter
import json

def generate_sample_xml(final_mappings, root_tag="DATA", row_tag="ROW"):
    xml = f"<{root_tag}>\n"
    xml += f"  <{row_tag}>\n"
    for m in final_mappings:
        tag = m['extracted_label'].replace(" ", "_").upper()
        xml += f"    <{tag}>SAMPLE_VALUE</{tag}>\n"
    xml += f"  </{row_tag}>\n</{root_tag}>"
    return xml

def generate_data_definition():
    return {
        "DataDefinition": {
            "Name": "R12_Report_Template",
            "Code": "R12_CUSTOM_TEMPLATE",
            "ApplicationShortName": "XXCUS",
            "DataTemplateCode": "XXCUS_R12_QUERY",
            "DefaultOutputType": "EXCEL"
        }
    }

def generate_excel_template(final_mappings):
    import io
    import xlsxwriter

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet("Template")

    # Row 0: Column headers
    for col_num, m in enumerate(final_mappings):
        worksheet.write_string(0, col_num, m['extracted_label'])

    # Row 1: XML BI Publisher tags, with for-each included only in the first tag
    for col_num, m in enumerate(final_mappings):
        xml_tag = m['extracted_label'].replace(" ", "_").upper()
        if col_num == 0:
            worksheet.write_string(1, col_num, f"<?for-each:ROW?><?{xml_tag}?>")
        else:
            worksheet.write_string(1, col_num, f"<?{xml_tag}?>")

    # Row 2: Close the for-each loop (only in first column)
    worksheet.write_string(2, 0, "<?end for-each?>")

    workbook.close()
    output.seek(0)
    return output
