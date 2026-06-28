from flask import Flask, request, jsonify
import pymysql
from datetime import datetime
import os
import random
import string
import json

app = Flask(__name__)

DB_HOST = os.environ.get('MYSQL_HOST', '10.13.103.5')
DB_PORT = int(os.environ.get('MYSQL_PORT', 3306))
DB_USER = os.environ.get('MYSQL_USER', 'root')
DB_PASS = os.environ.get('MYSQL_PASSWORD', 'VdhQ2XpY')
DB_NAME = os.environ.get('MYSQL_DB', 'shop')


def get_db():
    return pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
                           password=DB_PASS, database=DB_NAME, charset='utf8mb4')


def init_db():
    try:
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
                               password=DB_PASS, charset='utf8mb4')
        cursor = conn.cursor()
        cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4')
        conn.commit()
        cursor.close()
        conn.close()
        print(f'数据库 {DB_NAME} 就绪')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                openid VARCHAR(64) DEFAULT '',
                order_no VARCHAR(32) UNIQUE NOT NULL,
                products JSON,
                total_price DECIMAL(10,2) DEFAULT 0,
                delivery_fee DECIMAL(10,2) DEFAULT 0,
                final_price DECIMAL(10,2) DEFAULT 0,
                total_weight DECIMAL(10,2) DEFAULT 0,
                user_name VARCHAR(64) DEFAULT '',
                phone VARCHAR(20) DEFAULT '',
                address VARCHAR(255) DEFAULT '',
                door_number VARCHAR(64) DEFAULT '',
                remark VARCHAR(255) DEFAULT '',
                status VARCHAR(20) DEFAULT 'pending',
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()
        print('数据表 orders 就绪')
    except Exception as e:
        print(f'数据库初始化失败: {e}')


def generate_order_no():
    now = datetime.now()
    rand = ''.join(random.choices(string.digits, k=4))
    return now.strftime('%Y%m%d%H%M%S') + rand


@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    order_data = data.get('orderData', {})
    openid = request.headers.get('X-WX-OPENID', '')

    try:
        conn = get_db()
        cursor = conn.cursor()
        order_no = generate_order_no()
        cursor.execute('''
            INSERT INTO orders (openid, order_no, products, total_price, delivery_fee,
                final_price, total_weight, user_name, phone, address, door_number, remark, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            openid, order_no,
            json.dumps(order_data.get('products', []), ensure_ascii=False),
            order_data.get('totalPrice', 0),
            order_data.get('deliveryFee', 0),
            order_data.get('finalPrice', 0),
            order_data.get('totalWeight', 0),
            order_data.get('userName', ''),
            order_data.get('phone', ''),
            order_data.get('address', ''),
            order_data.get('doorNumber', ''),
            order_data.get('remark', ''),
            'pending'
        ))
        conn.commit()
        order_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'orderId': str(order_id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/orders', methods=['GET'])
def get_orders():
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('pageSize', 20))
    status = request.args.get('status', None)

    try:
        conn = get_db()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        where = ''
        params = []
        if status:
            where = 'WHERE status = %s'
            params.append(status)

        cursor.execute(f'SELECT COUNT(*) as total FROM orders {where}', params)
        total = cursor.fetchone()['total']

        params_for_query = params.copy()
        offset = (page - 1) * page_size
        params_for_query.extend([offset, page_size])
        cursor.execute(f'SELECT * FROM orders {where} ORDER BY create_time DESC LIMIT %s, %s', params_for_query)
        rows = cursor.fetchall()

        orders = []
        for row in rows:
            row['id'] = str(row['id'])
            row['products'] = json.loads(row['products']) if row['products'] else []
            row['total_price'] = float(row['total_price'])
            row['delivery_fee'] = float(row['delivery_fee'])
            row['final_price'] = float(row['final_price'])
            row['total_weight'] = float(row['total_weight'])
            row['create_time'] = row['create_time'].isoformat() if row.get('create_time') else None
            row['update_time'] = row['update_time'].isoformat() if row.get('update_time') else None
            orders.append(row)

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'list': orders,
                'total': total,
                'page': page,
                'pageSize': page_size
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/orders/<order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    data = request.get_json()
    status = data.get('status', '')

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE orders SET status = %s WHERE id = %s', (status, order_id))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 80))
    app.run(host='0.0.0.0', port=port, debug=False)
