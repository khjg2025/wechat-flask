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
                tracking_no VARCHAR(64) DEFAULT '',
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
    openid = request.args.get('openid', None)

    try:
        conn = get_db()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        where = []
        params = []
        if status:
            where.append('status = %s')
            params.append(status)
        if openid:
            where.append('openid = %s')
            params.append(openid)

        where_sql = 'WHERE ' + ' AND '.join(where) if where else ''

        cursor.execute(f'SELECT COUNT(*) as total FROM orders {where_sql}', params)
        total = cursor.fetchone()['total']

        params_for_query = params.copy()
        offset = (page - 1) * page_size
        params_for_query.extend([offset, page_size])
        cursor.execute(f'SELECT * FROM orders {where_sql} ORDER BY create_time DESC LIMIT %s, %s', params_for_query)
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
    tracking_no = data.get('tracking_no', '')

    try:
        conn = get_db()
        cursor = conn.cursor()
        if tracking_no:
            cursor.execute('UPDATE orders SET status = %s, tracking_no = %s WHERE id = %s', (status, tracking_no, order_id))
        else:
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


@app.route('/api/openid', methods=['GET'])
def get_openid():
    openid = request.headers.get('X-WX-OPENID', '')
    return jsonify({'openid': openid})


@app.route('/api/userinfo', methods=['GET'])
def get_userinfo():
    openid = request.headers.get('X-WX-OPENID', '')
    nickname = request.headers.get('X-WX-NICKNAME', '')
    avatar_url = request.headers.get('X-WX-HEADIMGURL', '')
    return jsonify({
        'openid': openid,
        'nickName': nickname or '用户',
        'avatarUrl': avatar_url or 'https://cdn-icons-png.flaticon.com/128/2928/2928892.png'
    })


@app.route('/api/admin')
def admin_page():
    conn = get_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute('SELECT * FROM orders ORDER BY create_time DESC')
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    import json
    orders = []
    for row in rows:
        row['products'] = json.loads(row['products']) if row['products'] else []
        row['total_price'] = float(row['total_price'])
        row['delivery_fee'] = float(row['delivery_fee'])
        row['final_price'] = float(row['final_price'])
        orders.append(row)

    status_map = {'pending': '待处理', 'paid': '已支付', 'shipped': '已发货', 'completed': '已完成'}
    rows_html = ''
    for o in orders:
        products_str = '<br>'.join([f"{p['name']} x{p['count']}" for p in o['products']])
        rows_html += f'''
        <tr>
            <td>{o['id']}</td>
            <td>{o['order_no']}</td>
            <td>{o['user_name']}</td>
            <td>{o['phone']}</td>
            <td>{o['address']} {o['door_number']}</td>
            <td>{products_str}</td>
            <td>¥{o['final_price']}</td>
            <td><span class="status {o['status']}">{status_map.get(o['status'], o['status'])}</span></td>
            <td>{o['openid']}</td>
            <td>{o['remark']}</td>
        </tr>'''

    html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>全部订单</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, sans-serif; background: #f5f5f5; padding: 20px; }}
  h1 {{ color: #333; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  th {{ background: #ff6b35; color: #fff; padding: 12px 10px; text-align: left; font-size: 14px; }}
  td {{ padding: 10px; border-bottom: 1px solid #eee; font-size: 13px; }}
  tr:hover {{ background: #f9f9f9; }}
  .status {{ padding: 4px 10px; border-radius: 12px; font-size: 12px; color: #fff; }}
  .status.pending {{ background: #ff9800; }}
  .status.paid {{ background: #2196f3; }}
  .status.shipped {{ background: #9c27b0; }}
  .status.completed {{ background: #4caf50; }}
  .count {{ color: #888; margin-bottom: 10px; }}
</style>
</head>
<body>
<h1>全部订单</h1>
<p class="count">共 {len(orders)} 条订单</p>
<table>
<tr>
  <th>ID</th><th>订单号</th><th>收货人</th><th>电话</th><th>地址</th>
  <th>商品</th><th>合计</th><th>状态</th><th>OpenID</th><th>备注</th>
</tr>
{rows_html}
</table>
</body>
</html>'''
    return html


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 80))
    app.run(host='0.0.0.0', port=port, debug=False)
