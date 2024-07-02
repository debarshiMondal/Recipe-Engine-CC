from flask import Flask, request, render_template, redirect, url_for, send_from_directory, flash
import shutil
import os
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from jinja2 import Environment, FileSystemLoader

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Ensure the required directories exist
os.makedirs('Recipes', exist_ok=True)
os.makedirs('Bazar', exist_ok=True)
os.makedirs('Recipes Send to Team', exist_ok=True)
os.makedirs('Methods', exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('Unit Costs', exist_ok=True)
os.makedirs('Price Setting and Cooking Instructions/Categories', exist_ok=True)

env = Environment(loader=FileSystemLoader('templates'))
env.globals.update(enumerate=enumerate, url_for=url_for)

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

    # Gather original recipe data
    original_recipes = []
    for f in os.listdir('Recipes'):
        if not f.startswith('~$'):
            parts = f.split('_')
            quantity_produced = parts[0][:-2]
            unit = parts[0][-2:]
            display_name = parts[1].replace('.xlsx', '').replace('_', ' ')
            original_recipes.append({'display_name': display_name, 'quantity_produced': quantity_produced, 'unit': unit})

    return render_template('upload_process_recipes.html', recipes=recipes, bazar_files=bazar_files, latest_bazar_file=latest_bazar_file, methods_files=methods_files, original_recipes=original_recipes)


@app.route('/process_recipes', methods=['GET', 'POST'])
def process_recipes():
    cost_list = []
    bazar_filename = None
    
    if request.method == 'POST':
        data = request.form.to_dict(flat=False)
        recipes = [{'filename': f, 'display_name': f.split('_')[1].replace('.xlsx', '').replace('_', ' ')} for f in os.listdir('Recipes') if not f.startswith('~$')]
        master_list = pd.DataFrame()

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

                df['Cost'] = df['Unit Cost'] * df[['Quantity (Gm)', 'Quantity (Pieces)']].max(axis=1)
                cost_per_unit = df['Cost'].sum() / quantity_produced

                recipe_display_name = recipe.split('_')[1].replace('.xlsx', '').replace('_', ' ')
                recipe_file_name = f"{quantity_produced} {unit} {recipe_display_name} Recipe.xlsx"
                
                cost_list.append({
                    'recipe': recipe_file_name,
                    'cost_per_unit': cost_per_unit,
                    'display_name': recipe_display_name
                })

                columns_to_keep = ['Ingredients', 'Quantity (Gm)', 'Quantity (Pieces)', 'Comment']
                df_team = df[columns_to_keep]

                df_team.to_excel(os.path.join('Recipes Send to Team', recipe_file_name), index=False)

                master_list = pd.concat([master_list, df[['Ingredients', 'Quantity (Gm)', 'Quantity (Pieces)', 'Unit Cost']]])

        if not master_list.empty:
            master_list = master_list.groupby('Ingredients').agg({
                'Quantity (Gm)': lambda x: sum(x) if x.name == 'Quantity (Gm)' else 0,
                'Quantity (Pieces)': lambda x: sum(x) if x.name == 'Quantity (Pieces)' else 0,
                'Unit Cost': 'mean'
            }).reset_index()

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

        selected_recipes = [recipe for i, recipe in enumerate(data.get('recipe', [])) if recipe and data['recipe_qty'][i]]
        quantities = [float(data['recipe_qty'][i]) for i in range(len(data['recipe_qty'])) if data['recipe_qty'][i]]
        units = [data['recipe_unit'][i] for i in range(len(data['recipe_unit'])) if data['recipe_unit'][i]]
        invoice_filename = generate_invoice(selected_recipes, quantities, units, cost_list)

    methods_files = [{'filename': f, 'display_name': f.replace('.pdf', '')} for f in os.listdir('Methods') if f.endswith('.pdf')]
    bazar_files = [f for f in os.listdir('Bazar') if not f.startswith('~$')]
    bazar_files = sorted(bazar_files, key=lambda x: os.path.getctime(os.path.join('Bazar', x)), reverse=True)
    latest_bazar_file = bazar_files[0] if bazar_files else None

    # Gather original recipe data
    original_recipes = []
    for f in os.listdir('Recipes'):
        if not f.startswith('~$'):
            parts = f.split('_')
            quantity_produced = parts[0][:-2]
            unit = parts[0][-2:]
            display_name = parts[1].replace('.xlsx', '').replace('_', ' ')
            original_recipes.append({'display_name': display_name, 'quantity_produced': quantity_produced, 'unit': unit})

    return render_template('process_recipes.html', recipes=recipes, costs=cost_list, bazar_file=latest_bazar_file, invoice_file=invoice_filename, original_recipes=original_recipes, methods_files=methods_files)

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
    

@app.route('/ccp_stock', methods=['GET', 'POST'])
def ccp_stock():
    original_recipes = sorted(
        [{'display_name': f.split('_')[1].replace('.xlsx', '').replace('_', ' '), 'quantity_produced': f.split('_')[0][:-2], 'unit': f.split('_')[0][-2:]}
         for f in os.listdir('Recipes') if not f.startswith('~$')], key=lambda x: x['display_name'])

    stock_file = 'Inventory/ccp_stock_data.xlsx'
    if os.path.exists(stock_file):
        stock_df = pd.read_excel(stock_file)
    else:
        stock_df = pd.DataFrame({'Product': [recipe['display_name'] for recipe in original_recipes],
                                 'Current Stock (Kg)': [''] * len(original_recipes),
                                 'Current Stock (Pieces)': [''] * len(original_recipes)})
        stock_df.to_excel(stock_file, index=False)

    threshold_kg = request.args.get('threshold_kg', 5)
    threshold_pieces = request.args.get('threshold_pieces', 25)
    filter_criteria = request.args.get('filter_criteria', '')

    if filter_criteria:
        try:
            # Ensure the filter criteria is treated as a string literal
            filter_criteria = filter_criteria.replace("'", "\\'")
            stock_df = stock_df[stock_df['Product'].str.contains(filter_criteria, case=False, na=False)]
        except Exception as e:
            return f"Error applying filter: {e}", 400

    if request.method == 'POST':
        if 'save' in request.form:
            stock_df.to_excel(stock_file, index=False)
            return redirect(url_for('ccp_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces))

        if 'set_threshold' in request.form:
            threshold_kg = int(request.form.get('threshold_kg', threshold_kg))
            threshold_pieces = int(request.form.get('threshold_pieces', threshold_pieces))
            return redirect(url_for('ccp_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces))

        if 'update' in request.form:
            product = request.form.get('product')
            update_value = request.form.get('update_stock', '')
            unit = request.form.get('unit')
            if unit == 'kg':
                stock_df.loc[stock_df['Product'] == product, 'Current Stock (Kg)'] = update_value
                stock_df.loc[stock_df['Product'] == product, 'Current Stock (Pieces)'] = ''
            elif unit == 'pieces':
                stock_df.loc[stock_df['Product'] == product, 'Current Stock (Pieces)'] = update_value
                stock_df.loc[stock_df['Product'] == product, 'Current Stock (Kg)'] = ''
            stock_df.to_excel(stock_file, index=False)
            return redirect(url_for('ccp_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces, filter_criteria=filter_criteria))

        if 'clear' in request.form:
            product = request.form.get('product')
            stock_df.loc[stock_df['Product'] == product, ['Current Stock (Kg)', 'Current Stock (Pieces)']] = ''
            stock_df.to_excel(stock_file, index=False)
            return redirect(url_for('ccp_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces, filter_criteria=filter_criteria))

    stock_df = stock_df.sort_values(by='Product')
    stock_data = stock_df.to_dict('records')

    for record in stock_data:
        if record.get('Current Stock (Kg)', '') and float(record.get('Current Stock (Kg)', 0)) <= float(threshold_kg):
            record['current_stock_kg_style'] = 'color: red; font-weight: bold;'
        else:
            record['current_stock_kg_style'] = ''
        
        if record.get('Current Stock (Pieces)', '') and float(record.get('Current Stock (Pieces)', 0)) <= float(threshold_pieces):
            record['current_stock_pieces_style'] = 'color: red; font-weight: bold;'
        else:
            record['current_stock_pieces_style'] = ''

    return env.get_template('ccp_stock.html').render(original_recipes=original_recipes, stock_data=stock_data, threshold_kg=threshold_kg, threshold_pieces=threshold_pieces, filter_criteria=filter_criteria)



@app.route('/clear_stock/<product>', methods=['POST'])
def clear_stock(product):
    stock_file = 'Inventory/ccp_stock_data.xlsx'
    stock_df = pd.read_excel(stock_file)

    if 'kg' in request.form:
        stock_df.loc[stock_df['Product'] == product, 'Current Stock (Kg)'] = 0
    if 'pieces' in request.form:
        stock_df.loc[stock_df['Product'] == product, 'Current Stock (Pieces)'] = 0

    stock_df.to_excel(stock_file, index=False)
    return redirect(url_for('ccp_stock'))

@app.route('/clear_all_stock', methods=['POST'])
def clear_all_stock():
    stock_file = 'Inventory/ccp_stock_data.xlsx'
    stock_df = pd.read_excel(stock_file)

    stock_df['Current Stock (Kg)'] = 0
    stock_df['Current Stock (Pieces)'] = 0

    stock_df.to_excel(stock_file, index=False)
    return redirect(url_for('ccp_stock'))

# Other routes remain unchanged

@app.route('/create_view', methods=['GET', 'POST'])
def create_view():
    if request.method == 'POST':
        view_name = request.form['view_name']
        filter_criteria = request.form['filter_criteria'] or 'None (All Products)'

        if not os.path.exists('views.csv'):
            with open('views.csv', 'w') as file:
                file.write('View Name,Filter Criteria\n')

        with open('views.csv', 'a') as file:
            file.write(f'{view_name},{filter_criteria}\n')

        return redirect(url_for('list_view'))

    return render_template('create_view.html')

@app.route('/list_view', methods=['GET'])
def list_view():
    views = []
    if os.path.exists('views.csv'):
        df = pd.read_csv('views.csv')
        views = df.to_dict('records')

    return render_template('list_view.html', views=views)

@app.route('/view/<view_name>', methods=['GET'])
def view(view_name):
    filter_criteria = None
    if os.path.exists('views.csv'):
        df = pd.read_csv('views.csv')
        view = df[df['View Name'] == view_name]
        if not view.empty:
            filter_criteria = view.iloc[0]['Filter Criteria']

    stock_file = 'Inventory/ccp_stock_data.xlsx'
    if os.path.exists(stock_file):
        stock_df = pd.read_excel(stock_file)
        if filter_criteria and filter_criteria != 'None (All Products)':
            try:
                stock_df = stock_df[stock_df['Product'].str.contains(filter_criteria, na=False)]
            except Exception as e:
                return f"Error applying filter: {e}"

        stock_data = stock_df.to_dict('records')
        return render_template('view.html', view_name=view_name, filter_criteria=filter_criteria, stock_data=stock_data)

    return "Stock data not found."

import shutil

def backup_file(file_path):
    """Creates a backup of the specified file."""
    backup_path = file_path.replace(".xlsx", "_backup.xlsx")
    shutil.copyfile(file_path, backup_path)


@app.route('/raw_material_stock', methods=['GET', 'POST'])
def raw_material_stock():
    stock_file = 'Inventory/Raw material list.xlsx'
    backup_file(stock_file)

    if os.path.exists(stock_file):
        stock_df = pd.read_excel(stock_file)
    else:
        # Define columns based on your Raw material list structure
        stock_df = pd.DataFrame({'Product': [], 'Current Stock (Kg)': [], 'Current Stock (Pieces)': [], 'Vendor': []})
        stock_df.to_excel(stock_file, index=False)

    threshold_kg = request.args.get('threshold_kg', 5)
    threshold_pieces = request.args.get('threshold_pieces', 25)

    if request.method == 'POST':
        if 'save' in request.form:
            stock_df.to_excel(stock_file, index=False)
            return redirect(url_for('raw_material_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces))

        if 'set_threshold' in request.form:
            threshold_kg = int(request.form.get('threshold_kg'))
            threshold_pieces = int(request.form.get('threshold_pieces'))
            return redirect(url_for('raw_material_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces))

        if 'update' in request.form:
            product = request.form.get('product')
            update_value = request.form.get('update_stock', '')
            unit = request.form.get('unit')
            if unit == 'kg':
                current_value = stock_df.loc[stock_df['Product'] == product, 'Current Stock (Kg)'].values[0]
                if pd.isna(current_value):
                    current_value = 0
                stock_df.loc[stock_df['Product'] == product, 'Current Stock (Kg)'] = float(current_value) + float(update_value)
            elif unit == 'pieces':
                current_value = stock_df.loc[stock_df['Product'] == product, 'Current Stock (Pieces)'].values[0]
                if pd.isna(current_value):
                    current_value = 0
                stock_df.loc[stock_df['Product'] == product, 'Current Stock (Pieces)'] = float(current_value) + float(update_value)
            stock_df.to_excel(stock_file, index=False)
            return redirect(url_for('raw_material_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces))

        if 'clear' in request.form:
            product = request.form.get('product')
            stock_df.loc[stock_df['Product'] == product, ['Current Stock (Kg)', 'Current Stock (Pieces)']] = ''
            stock_df.to_excel(stock_file, index=False)
            return redirect(url_for('raw_material_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces))

    stock_df = stock_df.sort_values(by='Product')
    stock_data = stock_df.to_dict('records')

    for record in stock_data:
        if record.get('Current Stock (Kg)', '') and float(record.get('Current Stock (Kg)', 0)) <= float(threshold_kg):
            record['current_stock_kg_style'] = 'color: red; font-weight: bold;'
        else:
            record['current_stock_kg_style'] = ''
        
        if record.get('Current Stock (Pieces)', '') and float(record.get('Current Stock (Pieces)', 0)) <= float(threshold_pieces):
            record['current_stock_pieces_style'] = 'color: red; font-weight: bold;'
        else:
            record['current_stock_pieces_style'] = ''

    return env.get_template('raw_material_stock.html').render(stock_data=stock_data, threshold_kg=threshold_kg, threshold_pieces=threshold_pieces)


@app.route('/op_stock', methods=['GET', 'POST'])
def op_stock():
    stock_file = 'Inventory/op_stock_data.xlsx'
    backup_file(stock_file)

    original_recipes = sorted(
        [{'display_name': f.split('_')[1].replace('.xlsx', '').replace('_', ' '), 'quantity_produced': f.split('_')[0][:-2], 'unit': f.split('_')[0][-2:]}
         for f in os.listdir('Recipes') if not f.startswith('~$')], key=lambda x: x['display_name'])

    if os.path.exists(stock_file):
        stock_df = pd.read_excel(stock_file)
    else:
        stock_df = pd.DataFrame({'Product': [recipe['display_name'] for recipe in original_recipes],
                                 'Current Stock (Kg)': [''] * len(original_recipes),
                                 'Current Stock (Pieces)': [''] * len(original_recipes),
                                 'Vendor': [''] * len(original_recipes)})
        stock_df.to_excel(stock_file, index=False)

    threshold_kg = request.args.get('threshold_kg', 5)
    threshold_pieces = request.args.get('threshold_pieces', 25)

    if request.method == 'POST':
        if 'save' in request.form:
            stock_df.to_excel(stock_file, index=False)
            return redirect(url_for('op_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces))

        if 'set_threshold' in request.form:
            threshold_kg = int(request.form.get('threshold_kg'))
            threshold_pieces = int(request.form.get('threshold_pieces'))
            return redirect(url_for('op_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces))

        if 'update' in request.form:
            product = request.form.get('product')
            update_value = request.form.get('update_stock', '')
            unit = request.form.get('unit')
            if unit == 'kg':
                current_value = stock_df.loc[stock_df['Product'] == product, 'Current Stock (Kg)'].values[0]
                if pd.isna(current_value):
                    current_value = 0
                stock_df.loc[stock_df['Product'] == product, 'Current Stock (Kg)'] = float(current_value) + float(update_value)
            elif unit == 'pieces':
                current_value = stock_df.loc[stock_df['Product'] == product, 'Current Stock (Pieces)'].values[0]
                if pd.isna(current_value):
                    current_value = 0
                stock_df.loc[stock_df['Product'] == product, 'Current Stock (Pieces)'] = float(current_value) + float(update_value)
            stock_df.to_excel(stock_file, index=False)
            return redirect(url_for('op_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces))

        if 'clear' in request.form:
            product = request.form.get('product')
            stock_df.loc[stock_df['Product'] == product, ['Current Stock (Kg)', 'Current Stock (Pieces)']] = ''
            stock_df.to_excel(stock_file, index=False)
            return redirect(url_for('op_stock', threshold_kg=threshold_kg, threshold_pieces=threshold_pieces))

    stock_df = stock_df.sort_values(by='Product')
    stock_data = stock_df.to_dict('records')

    for record in stock_data:
        if record.get('Current Stock (Kg)', '') and float(record.get('Current Stock (Kg)', 0)) <= float(threshold_kg):
            record['current_stock_kg_style'] = 'color: red; font-weight: bold;'
        else:
            record['current_stock_kg_style'] = ''
        
        if record.get('Current Stock (Pieces)', '') and float(record.get('Current Stock (Pieces)', 0)) <= float(threshold_pieces):
            record['current_stock_pieces_style'] = 'color: red; font-weight: bold;'
        else:
            record['current_stock_pieces_style'] = ''

    return env.get_template('op_stock.html').render(original_recipes=original_recipes, stock_data=stock_data, threshold_kg=threshold_kg, threshold_pieces=threshold_pieces)


@app.route('/op_purchase_order', methods=['GET'])
def op_purchase_order():
    # Logic for handling O-P purchase order page
    return render_template('op_purchase_order.html')


@app.route('/cooking_methods', methods=['GET'])
def cooking_methods():
    methods_files = [{'filename': f, 'display_name': f.replace('.pdf', '')} for f in os.listdir('Methods') if f.endswith('.pdf')]
    return render_template('cooking_methods.html', methods_files=methods_files)
    
@app.route('/cooking_methods_page', methods=['GET'])
def cooking_methods_page():
    methods_files = [{'filename': f, 'display_name': f.replace('.pdf', '')} for f in os.listdir('Methods') if f.endswith('.pdf')]
    return render_template('cooking_methods_page.html', methods_files=methods_files)

@app.route('/price_setting_page', methods=['GET'])
def price_setting_page():
    return render_template('price_setting_page.html')

@app.route('/price_setting_instructions', methods=['GET', 'POST'])
def price_setting_instructions():
    if request.method == 'POST':
        if 'create_category' in request.form:
            new_category = request.form['category_name']
            if new_category:
                with open('Price Setting and Cooking Instructions/categories.txt', 'a') as file:
                    file.write(f"{new_category}\n")
                flash('Category created successfully!', 'success')
            return redirect(url_for('price_setting_instructions'))
        if 'delete_category' in request.form:
            category_to_delete = request.form['category_name']
            if category_to_delete:
                with open('Price Setting and Cooking Instructions/categories.txt', 'r') as file:
                    categories = file.readlines()
                with open('Price Setting and Cooking Instructions/categories.txt', 'w') as file:
                    for category in categories:
                        if category.strip() != category_to_delete:
                            file.write(category)
                flash('Category deleted successfully!', 'success')
            return redirect(url_for('price_setting_instructions'))

    categories = fetch_categories()
    dropdown_data = {}

    # Fetch data for dropdowns
    for category in categories:
        file_path = os.path.join('Price Setting and Cooking Instructions/Data Base', f'{category}.xlsx')
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            dropdown_data[category] = df.to_dict('records')

    return render_template('price_setting_instructions.html', categories=categories, dropdown_data=dropdown_data)



@app.route('/delete_category', methods=['POST'])
def delete_category():
    category = request.form.get('category')
    if category:
        category_path = os.path.join('Price Setting and Cooking Instructions/Categories', f'{category}.txt')
        if os.path.exists(category_path):
            os.remove(category_path)
            flash('Category deleted successfully!', 'success')
        else:
            flash('Category not found!', 'error')
    return redirect(url_for('price_setting_instructions'))


@app.route('/create_dish', methods=['POST'])
def create_dish():
    dish_name = request.form.get('dish_name')
    print(f"Dish Name received: {dish_name}")  # Debugging statement

    # Logic to handle dish creation
    flash(f'Dish "{dish_name}" created successfully!', 'success')

    # Fetch categories
    categories = fetch_categories()

    # Fetch data for dropdowns
    dropdown_data = {}
    for category in categories:
        file_path = os.path.join('Price Setting and Cooking Instructions/Data Base', f'{category}.xlsx')
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            print(f"Columns in {category}: {df.columns}")  # Debugging statement
            if 'name' in df.columns and 'unit_cost' in df.columns:
                dropdown_data[category] = df[['name', 'unit_cost']].to_dict('records')
            elif 'name' in df.columns and 'Unit Cost' in df.columns:
                df['unit_cost'] = df['Unit Cost']
                dropdown_data[category] = df[['name', 'unit_cost']].to_dict('records')
            else:
                print(f"Unexpected columns in {file_path}: {df.columns}")

    # Fetch raw materials and packaging materials
    raw_materials = []
    packaging_materials = []
    raw_materials_path = 'Inventory/Raw material list.xlsx'
    packaging_materials_path = 'Inventory/Packaging material list.xlsx'

    if os.path.exists(raw_materials_path):
        df_raw = pd.read_excel(raw_materials_path)
        print(f"Raw Materials Columns: {df_raw.columns}")  # Debugging statement
        if 'Product' in df_raw.columns and 'Unit Cost' in df_raw.columns:
            df_raw['unit_cost'] = df_raw['Unit Cost']
            raw_materials = df_raw[['Product', 'unit_cost']].to_dict('records')
        else:
            print(f"Expected columns 'Product' and 'Unit Cost' not found in {raw_materials_path}")

    if os.path.exists(packaging_materials_path):
        df_packaging = pd.read_excel(packaging_materials_path)
        print(f"Packaging Materials Columns: {df_packaging.columns}")  # Debugging statement
        if 'Product' in df_packaging.columns and 'Unit Cost' in df_packaging.columns:
            df_packaging['unit_cost'] = df_packaging['Unit Cost']
            packaging_materials = df_packaging[['Product', 'unit_cost']].to_dict('records')
        else:
            print(f"Expected columns 'Product' and 'Unit Cost' not found in {packaging_materials_path}")

    # Debugging output
    print("Dropdown Data:", dropdown_data)
    print("Raw Materials:", raw_materials)
    print("Packaging Materials:", packaging_materials)

    return render_template('price_setting_instructions.html', 
                           categories=categories, 
                           dropdown_data=dropdown_data, 
                           dish_name=dish_name,
                           raw_materials=raw_materials, 
                           packaging_materials=packaging_materials)



def fetch_raw_materials():
    file_path = 'Inventory/Raw material list.xlsx'
    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        if 'Product' in df.columns:
            return df[['Product']].to_dict('records')
    return []

def fetch_packaging_materials():
    file_path = 'Inventory/Packaging material list.xlsx'
    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        if 'Product' in df.columns:
            return df[['Product']].to_dict('records')
    return []


def fetch_categories():
    categories = []
    if os.path.exists('Price Setting and Cooking Instructions/categories.txt'):
        with open('Price Setting and Cooking Instructions/categories.txt', 'r') as file:
            categories = [line.strip() for line in file]
    return categories

def categorize_products(cc_products, op_products, categories):
    categorized_data = {category: [] for category in categories}

    for product in cc_products + op_products:
        for category in categories:
            if category.lower() in product['name'].lower():
                categorized_data[category].append(product)
                break

    return categorized_data

def update_excel_files(categorized_data):
    base_path = 'Price Setting and Cooking Instructions/Data Base'
    os.makedirs(base_path, exist_ok=True)
    
    for category, products in categorized_data.items():
        file_path = os.path.join(base_path, f"{category}.xlsx")
        df = pd.DataFrame(products)
        df.to_excel(file_path, index=False)
        print(f"Updated {file_path} with products: {products}")

@app.route('/categorize_products', methods=['POST'])
def categorize_products_route():
    # Implement the logic to categorize products and create the excel files
    cc_products = fetch_cc_products()
    op_products = fetch_op_products()

    # Fetch categories
    categories = []
    if os.path.exists('Price Setting and Cooking Instructions/categories.txt'):
        with open('Price Setting and Cooking Instructions/categories.txt', 'r') as file:
            categories = [line.strip() for line in file]

    # Create a DataFrame for each category
    for category in categories:
        category_products = []
        for product in cc_products + op_products:
            if category.lower() in product['name'].lower():
                category_products.append(product)

        if category_products:
            df = pd.DataFrame(category_products)
            file_path = os.path.join('Price Setting and Cooking Instructions/Data Base', f'{category}.xlsx')
            df.to_excel(file_path, index=False)
    
    flash('Data Base created successfully!', 'success')
    return redirect(url_for('price_setting_instructions'))



def fetch_cc_products():
    products = []
    for file in os.listdir('Recipes'):
        if file.endswith('.xlsx') and not file.startswith('~$'):
            try:
                parts = file.split('_')
                unit_quantity, product_name = parts[0], '_'.join(parts[1:]).replace('.xlsx', '')
                unit = 'Kg' if 'kg' in unit_quantity else 'pieces'
                # Handle the case where quantity starts with a dot
                quantity_str = unit_quantity.replace('kg', '').replace('pieces', '')
                if quantity_str.startswith('.'):
                    quantity_str = '0' + quantity_str
                quantity = float(quantity_str)
                
                df = pd.read_excel(os.path.join('Recipes', file))
                if 'Price' in df.columns:
                    total_cost = df['Price'].sum()
                    unit_cost = total_cost / quantity if quantity != 0 else 0
                    products.append({'name': product_name, 'unit': unit, 'unit_cost': unit_cost})
            except Exception as e:
                print(f"Error processing file {file}: {e}")
    return products


def fetch_op_products():
    df = pd.read_excel('Inventory/op_stock_data.xlsx')
    products = []
    for _, row in df.iterrows():
        product_name = row['Product']
        vendor = row['Vendor']
        unit = row['Unit']  # Make sure this column exists in your Excel file
        unit_cost = row['Our Unit Cost']
        products.append({'name': f"{product_name} ({vendor})", 'unit': unit, 'unit_cost': unit_cost})
    return products



def fetch_raw_materials():
    df = pd.read_excel('Inventory/Raw material list.xlsx')
    products = []
    for _, row in df.iterrows():
        product_name = row['Product']
        unit = row['Unit']
        unit_cost = row['Unit Cost']
        products.append({'name': product_name, 'unit': unit, 'unit_cost': unit_cost})
    return products


@app.route('/unit_costs', methods=['GET'])
def unit_costs():
    cc_products = fetch_cc_products()
    op_products = fetch_op_products()
    raw_materials = fetch_raw_materials()
    return render_template('unit_costs.html', cc_products=cc_products, op_products=op_products, raw_materials=raw_materials)

@app.route('/download_cc_products', methods=['GET'])
def download_cc_products():
    cc_products = fetch_cc_products()
    df = pd.DataFrame(cc_products)
    file_path = os.path.join('Unit Costs', 'cc_products.xlsx')
    df.to_excel(file_path, index=False)
    return send_from_directory('Unit Costs', 'cc_products.xlsx')

@app.route('/download_op_products', methods=['GET'])
def download_op_products():
    op_products = fetch_op_products()
    df = pd.DataFrame(op_products)
    file_path = os.path.join('Unit Costs', 'op_products.xlsx')
    df.to_excel(file_path, index=False)
    return send_from_directory('Unit Costs', 'op_products.xlsx')

@app.route('/download_raw_materials', methods=['GET'])
def download_raw_materials():
    raw_materials = fetch_raw_materials()
    df = pd.DataFrame(raw_materials)
    file_path = os.path.join('Unit Costs', 'raw_materials.xlsx')
    df.to_excel(file_path, index=False)
    return send_from_directory('Unit Costs', 'raw_materials.xlsx')
    


@app.route('/pos', methods=['GET'])
def pos():
    return render_template('pos.html')

if __name__ == '__main__':
    app.run(debug=True)