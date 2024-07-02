from flask import Flask, request, render_template, redirect, url_for, send_from_directory
import os
import pandas as pd
from datetime import datetime
from fpdf import FPDF

app = Flask(__name__)

# Ensure the required directories exist
os.makedirs('Recipes', exist_ok=True)
os.makedirs('Bazar', exist_ok=True)
os.makedirs('Recipes Send to Team', exist_ok=True)
os.makedirs('Methods', exist_ok=True)
os.makedirs('static', exist_ok=True)

def clean_old_files(folder):
    """Remove all files from the specified folder."""
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)

def generate_invoice(recipes, quantities, units, costs):
    """Generate a PDF invoice based on the recipes and quantities."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Header
    pdf.image('static/CC Logo.png', 10, 8, 33)
    pdf.cell(200, 10, txt="", ln=True, align='C')  # Empty cell for spacing
    pdf.cell(200, 10, txt="Estimated Invoice", ln=True, align='C')
    pdf.cell(200, 10, txt="Culinary Cravings Food and Hospitality Services L.L.P", ln=True, align='C')
    pdf.cell(200, 10, txt="66, Purbachal Road, A.P Nagar, Sonarpur, Kolkata - 700150", ln=True, align='C')
    pdf.cell(200, 10, txt="Phone: +91 8582-869-687", ln=True, align='C')
    pdf.cell(200, 10, txt="Email: culinarycravings050124@gmail.com", ln=True, align='C')
    pdf.cell(200, 10, txt="", ln=True, align='C')  # Blank line

    # Table Header
    pdf.cell(100, 10, txt="Product", border=1, ln=0, align='C')
    pdf.cell(50, 10, txt="Quantity", border=1, ln=0, align='C')
    pdf.cell(50, 10, txt="Unit", border=1, ln=0, align='C')
    pdf.cell(40, 10, txt="Cost", border=1, ln=1, align='C')

    total_cost = 0
    for i, recipe in enumerate(recipes):
        if 'kg_' in recipe:
            product_name = recipe.split('kg_')[1].replace('.xlsx', '').replace('_', ' ')
        else:
            product_name = recipe.split('pieces_')[1].replace('.xlsx', '').replace('_', ' ')
        pdf.cell(100, 10, txt=product_name, border=1, ln=0, align='C')
        pdf.cell(50, 10, txt=str(quantities[i]), border=1, ln=0, align='C')
        pdf.cell(50, 10, txt=units[i], border=1, ln=0, align='C')
        total_cost_for_recipe = quantities[i] * costs[i]['cost_per_unit']
        pdf.cell(40, 10, txt=str(total_cost_for_recipe), border=1, ln=1, align='C')
        total_cost += total_cost_for_recipe

    pdf.cell(200, 10, txt="", ln=True, align='C')  # Blank line
    pdf.cell(200, 10, txt="Total Cost: " + str(total_cost), ln=True, align='R')

    invoice_filename = "Invoice_" + datetime.now().strftime('%d-%B-%Y_%H-%M-%S') + ".pdf"
    pdf.output(os.path.join('static', invoice_filename))

    return invoice_filename

@app.route('/', methods=['GET'])
def home():
    return redirect(url_for('home_page'))

@app.route('/home', methods=['GET'])
def home_page():
    return render_template('home.html')

@app.route('/upload_process_recipes', methods=['GET', 'POST'])
def upload_process_recipes():
    if request.method == 'POST':
        file = request.files['file']
        quantity_produced = request.form['quantity_produced']
        recipe_name = request.form['recipe_name']
        unit = request.form['unit']
        
        if file.filename == '':
            return "No selected file"
        
        formatted_name = f"{quantity_produced}{unit}_{recipe_name}.xlsx"
        save_path = os.path.join('Recipes', formatted_name)
        file.save(save_path)
        return redirect(url_for('upload_process_recipes'))
    
    recipes = [{'filename': f, 'display_name': f.split('_')[1].replace('.xlsx', '').replace('_', ' ')} for f in os.listdir('Recipes') if not f.startswith('~$')]
    bazar_files = [f for f in os.listdir('Bazar') if not f.startswith('~$')]
    bazar_files = sorted(bazar_files, key=lambda x: os.path.getctime(os.path.join('Bazar', x)), reverse=True)
    latest_bazar_file = bazar_files[0] if bazar_files else None
    methods_files = [{'filename': f, 'display_name': f.replace('.pdf', '')} for f in os.listdir('Methods') if f.endswith('.pdf')]
    return render_template('upload_process_recipes.html', recipes=recipes, bazar_files=bazar_files, latest_bazar_file=latest_bazar_file, methods_files=methods_files)
@app.route('/process_recipes', methods=['POST'])
def process_recipes():
    data = request.form.to_dict(flat=False)
    recipes = [{'filename': f, 'display_name': f.split('_')[1].replace('.xlsx', '').replace('_', ' ')} for f in os.listdir('Recipes') if not f.startswith('~$')]
    master_list = pd.DataFrame()
    cost_list = []
    bazar_filename = None

    clean_old_files('Recipes Send to Team')

    for i, recipe in enumerate(data.get('recipe', [])):
        if recipe and data['recipe_qty'][i]:
            df = pd.read_excel(os.path.join('Recipes', recipe))
            quantity_produced = float(data['recipe_qty'][i])
            unit = data['recipe_unit'][i]
            original_quantity = float(recipe.split(unit+'_')[0].replace(unit, ''))
            scale_factor = quantity_produced / original_quantity

            df['Quantity (Gm)'] *= scale_factor
            df['Quantity (Pieces)'] *= scale_factor

            # Calculate cost per unit based on original quantity
            df['Cost'] = df['Unit Cost'] * df[['Quantity (Gm)', 'Quantity (Pieces)']].max(axis=1)
            cost_per_unit = df['Cost'].sum() / quantity_produced

            recipe_display_name = recipe.split('_')[1].replace('.xlsx', '').replace('_', ' ')
            recipe_file_name = f"{quantity_produced} {unit} {recipe_display_name} Recipe.xlsx"
            
            cost_list.append({
                'recipe': recipe_file_name,
                'cost_per_unit': cost_per_unit,
                'display_name': recipe_display_name
            })

            # Keep only the required columns for Recipes Send to Team
            columns_to_keep = ['Ingredients', 'Quantity (Gm)', 'Quantity (Pieces)', 'Comment']
            df_team = df[columns_to_keep]

            # Save individual files to Recipes Send to Team
            df_team.to_excel(os.path.join('Recipes Send to Team', recipe_file_name), index=False)

            # Append to the master list for Bazar
            master_list = pd.concat([master_list, df[['Ingredients', 'Quantity (Gm)', 'Quantity (Pieces)', 'Unit Cost']]])
    # Handle the Bazar file creation
    if not master_list.empty:
        master_list = master_list.groupby('Ingredients').agg({
            'Quantity (Gm)': 'sum',
            'Quantity (Pieces)': 'sum',
            'Unit Cost': 'mean'
        }).reset_index()

        # Calculate the Price column
        master_list['Price'] = master_list.apply(
            lambda row: row['Unit Cost'] * row['Quantity (Gm)'] if row['Quantity (Gm)'] > 0 else row['Unit Cost'] * row['Quantity (Pieces)'],
            axis=1
        )

        total_row = pd.DataFrame([{
            'Ingredients': 'Total',
            'Quantity (Gm)': master_list['Quantity (Gm)'].sum(),
            'Quantity (Pieces)': master_list['Quantity (Pieces)'].sum(),
            'Unit Cost': '',
            'Price': master_list['Price'].sum()
        }])
        master_list = pd.concat([master_list, total_row], ignore_index=True)

        date_str = datetime.now().strftime('%d-%B-%Y_%H-%M-%S')
        bazar_filename = f"All_Ingredients_for_Production_{date_str}.xlsx"
        master_list.to_excel(os.path.join('Bazar', bazar_filename), index=False)

    # Generate the invoice
    selected_recipes = [recipe for i, recipe in enumerate(data.get('recipe', [])) if recipe and data['recipe_qty'][i]]
    quantities = [float(data['recipe_qty'][i]) for i in range(len(data['recipe_qty'])) if data['recipe_qty'][i]]
    units = [data['recipe_unit'][i] for i in range(len(data['recipe_unit'])) if data['recipe_unit'][i]]
    invoice_filename = generate_invoice(selected_recipes, quantities, units, cost_list)

    # Fetch latest files from Methods and Bazar directories
    methods_files = [{'filename': f, 'display_name': f.replace('.pdf', '')} for f in os.listdir('Methods') if f.endswith('.pdf')]
    bazar_files = [f for f in os.listdir('Bazar') if not f.startswith('~$')]
    bazar_files = sorted(bazar_files, key=lambda x: os.path.getctime(os.path.join('Bazar', x)), reverse=True)
    latest_bazar_file = bazar_files[0] if bazar_files else None

    return render_template('upload_process_recipes.html', recipes=recipes, costs=cost_list, bazar_file=bazar_filename, invoice_file=invoice_filename, latest_bazar_file=latest_bazar_file, methods_files=methods_files)

@app.route('/Recipes Send to Team/<filename>')
def download_team_file(filename):
    return send_from_directory('Recipes Send to Team', filename)
@app.route('/Bazar/<filename>')
def download_bazar_file(filename):
    return send_from_directory('Bazar', filename)

@app.route('/static/<filename>')
def download_invoice(filename):
    return send_from_directory('static', filename)

@app.route('/Methods', methods=['POST'])
def upload_method():
    if 'file' not in request.files:
        return redirect(url_for('home_page'))
    file = request.files['file']
    if file and file.filename.endswith('.pdf'):
        filename = file.filename
        file.save(os.path.join('Methods', filename))
    return redirect(url_for('cooking_methods'))

@app.route('/Methods/<filename>')
def download_method(filename):
    return send_from_directory('Methods', filename)

@app.route('/inventory_order', methods=['GET'])
def inventory_order():
    return render_template('inventory_order.html')

@app.route('/cooking_methods', methods=['GET'])
def cooking_methods():
    methods_files = [{'filename': f, 'display_name': f.replace('.pdf', '')} for f in os.listdir('Methods') if f.endswith('.pdf')]
    return render_template('cooking_methods.html', methods_files=methods_files)

@app.route('/pos', methods=['GET'])
def pos():
    return render_template('pos.html')

if __name__ == '__main__':
    app.run(debug=True)
