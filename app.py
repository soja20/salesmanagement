from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:%40soja@localhost/sales_management'
app.config['JWT_SECRET_KEY'] = 'comego'

db = SQLAlchemy(app)
jwt = JWTManager(app)

#Model

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(10), default='user')
    sales = db.relationship('Sale', backref='user', lazy=True)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date_of_sale = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), default='pending')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

#connect sql

with app.app_context():
    db.create_all()

#performing endpoints
@app.route('/register', methods=['POST'])
def register():
    username = request.json.get('username')
    password = request.json.get('password')
    role = request.json.get('role', 'user')  
    new_user = User(username=username, password=password, role=role)
    db.session.add(new_user)
    db.session.commit()
    return jsonify(message="User registered successfully"), 201

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    user = User.query.filter_by(username=username, password=password).first()
    if user:
        access_token = create_access_token(identity={'id': user.id, 'role': user.role})
        return jsonify(access_token=access_token), 200
    return jsonify(message="Bad credentials"), 401

@app.route('/sales', methods=['POST'])
@jwt_required()
def create_sale():
    current_user = get_jwt_identity()  

    user_id = current_user.get('id')
    
    print(f"Current user from JWT: {current_user}")  
    if not current_user:
        return jsonify({"msg": "Invalid token or user identity not found"}), 401
    
    user_role = current_user.get('role') 
    print(f"User role: {user_role}")

    product_name = request.json.get('product_name')
    amount = request.json.get('amount')
    date_of_sale = request.json.get('date_of_sale')
    status = request.json.get('status')
    requested_user_id = request.json.get('user_id')

    if user_role == 'admin':
        user_id = request.json.get('user_id') 
        if not requested_user_id:
            return jsonify({"msg": "Admin must provide user_id to create sales for other users"}), 400
    else:
        if requested_user_id and requested_user_id != user_id:
            return jsonify({"msg": "Regular users cannot create sales for other users"}), 403
        
        requested_user_id = user_id

    sale = Sale(
        product_name=product_name,
        amount=amount,
        date_of_sale=datetime.strptime(date_of_sale, '%Y-%m-%d').date(),
        status=status,
        user_id=user_id
    )

    db.session.add(sale)
    db.session.commit()

    return jsonify(message="Sale record created"), 201


@app.route('/sales', methods=['GET'])
@jwt_required()
def get_sales():
    user = get_jwt_identity()
    user_id = user['id']
    if user['role'] == 'admin':
        sales = Sale.query.all()
    else:

        sales = Sale.query.filter_by(user_id=user_id).all()

    sales_list = [{'id': sale.id, 'user_id': sale.user_id, 'product_name':sale.product_name,'amount': sale.amount, 'date': sale.date_of_sale} for sale in sales]

    return jsonify(sales_list), 200

@app.route('/sales/<int:id>', methods=['GET'])
@jwt_required()
def get_sale(id):
    current_user = get_jwt_identity()  
    sale = Sale.query.get(id)

    if sale is None:
        return jsonify({"message": "Sale not found."}), 404

    if current_user['role'] != 'admin' and sale.user_id != current_user['id']:
        return jsonify({"message": "You can only access your own sales."}), 403

    return jsonify({
        "id": sale.id,
        "user_id": sale.user_id,
        "product_name":sale.product_name,
        "amount": sale.amount,
        "date":sale.date_of_sale
    }), 200


@app.route('/sales/<int:id>', methods=['PUT'])
@jwt_required()
def update_sale(id):
    current_user = get_jwt_identity()
    sale = Sale.query.get(id)
    if not sale:
        return jsonify(message="Sale not found"), 404

    if current_user['role'] != 'admin' or sale.user_id == current_user['id']:
        return jsonify({"message": "Access forbidden: You can only update your own sales."}), 403
    data=request.json
    product_name = data.get('product_name')
    amount = data.get('amount')
    date_of_sale= data.get('date_of_sale')
    status = data.get('status')

    if product_name:
        sale.product_name = product_name
    if amount is not None:
        sale.amount = amount
    if date_of_sale:
        sale.date_of_sale = date_of_sale
    if status:
        sale.status = status

    db.session.commit()

    return jsonify({
        "message": "Sale updated successfully.",
        "sale": {
            "id": sale.id,
            "user_id": sale.user_id,
            "product_name": sale.product_name,
            "amount": sale.amount,
            "date_of_sale": sale.date_of_sale,
            "status": sale.status
        }
    }), 200
@app.route('/sales/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_sale(id):
    current_user = get_jwt_identity()
    sale = Sale.query.get(id)
    if not sale:
        return jsonify(message="Sale not found"), 404

    if current_user['role'] == 'admin' or sale.user_id == current_user['id']:
        db.session.delete(sale)
        db.session.commit()
        return jsonify(message="Sale deleted successfully"), 200

    return jsonify(message="Unauthorized"), 403

if __name__ == '__main__':
    app.run(debug=True)
