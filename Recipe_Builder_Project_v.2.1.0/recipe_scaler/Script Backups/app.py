from flask import Flask, request, render_template, redirect, url_for, send_from_directory
import os
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from jinja2 import Environment, FileSystemLoader

app = Flask(__name__)

# Ensure the required directories exist
os.makedirs('Recipes', exist_ok=True)
os.makedirs('Bazar', exist_ok=True)
os.makedirs('Recipes Send to Team', exist_ok=True)
os.makedirs('Methods', exist_ok=True)
os.makedirs('static', exist_ok=True)

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



@app.route('/raw_material_stock', methods=['GET'])
def raw_material_stock():
    # Logic for handling raw material stock page
    return render_template('raw_material_stock.html')

@app.route('/op_stock', methods=['GET'])
def op_stock():
    # Logic for handling O-P stock page
    return render_template('op_stock.html')

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

@app.route('/price_setting_page', methods=['GET', 'POST'])
def price_setting_page():
    if request.method == 'POST':
        # Collect form data
        product_name = request.form.get('product_name')
        price = request.form.get('price')
        instructions = request.form.get('instructions')
        
        # Save the data (for simplicity, we'll use a CSV file)
        if not os.path.exists('price_settings.csv'):
            with open('price_settings.csv', 'w') as file:
                file.write('Product Name,Price,Instructions\n')
        
        with open('price_settings.csv', 'a') as file:
            file.write(f'{product_name},{price},{instructions}\n')
        
        return redirect(url_for('price_setting_page'))

    # Load existing data
    price_settings = []
    if os.path.exists('price_settings.csv'):
        df = pd.read_csv('price_settings.csv')
        price_settings = df.to_dict('records')
    
    return render_template('price_setting_page.html', price_settings=price_settings)
 


@app.route('/pos', methods=['GET'])
def pos():
    return render_template('pos.html')

if __name__ == '__main__':
    app.run(debug=True)