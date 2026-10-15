def test_customer_phone_is_saved_and_copied_to_shipment_destination(client):
    from app.tests.test_end_to_end import setup_flow
    setup_flow(client,'phone')
    payload={'customer_code':'PHONE-01','customer_name':'ลูกค้าเบอร์โทร','phone':'081-234-5678','address_line1':'99 บ้านตัวอย่าง','province':'กรุงเทพมหานคร'}
    response=client.post('/api/customers',json=payload)
    assert response.status_code==201,response.text
    customer=response.json()
    assert customer['phone']==payload['phone']
    assert next(c for c in client.get('/api/customers').json() if c['id']==customer['id'])['phone']==payload['phone']
    shipment=client.post('/api/shipments',json={'customer_id':customer['id'],'origin_warehouse_id':client.get('/api/warehouses').json()[0]['id'],'items':[{'product_id':client.get('/api/products').json()[0]['id'],'planned_quantity':1}]})
    assert shipment.status_code==201,shipment.text
    detail=client.get(f'/api/shipments/{shipment.json()["id"]}').json()
    assert detail['destination_phone']==payload['phone']
    assert payload['address_line1'] in detail['destination_address']
