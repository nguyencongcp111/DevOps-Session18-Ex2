# StoreX

Backend giả lập gồm ba service Spring Boot, gửi log JSON qua TCP tới Logstash, rồi vào Elasticsearch và Kibana.

```
user-service    (8081, userdb)  --\
order-service   (8082, orderdb) ---+--TCP:5000 (JSON)--> Logstash --> Elasticsearch --> Kibana (5601)
payment-service (8083, không DB) -/
   order-service --REST--> user-service     (kiểm tra user trước khi tạo đơn)
   order-service --REST--> payment-service  (thanh toán đơn hàng)
```

| Thành phần | Port trên host |
|---|---|
| user-service | 127.0.0.1:8081 |
| order-service | 127.0.0.1:8082 |
| payment-service | 127.0.0.1:8083 |
| PostgreSQL | 127.0.0.1:5434 |
| Logstash (tcp input) | 127.0.0.1:5000 |
| Elasticsearch | 127.0.0.1:9200 |
| Kibana | 127.0.0.1:5601 |

## Chạy

```bash
docker compose up -d --build
docker compose ps
```

## Thử bằng curl

```bash
# user-service (đã seed 2 user: id 1 và 2)
curl -s localhost:8081/api/users

# order-service: tạo đơn rồi thanh toán
curl -s -X POST localhost:8082/api/orders -H 'Content-Type: application/json' \
  -d '{"userId":1,"productName":"Ban phim co","quantity":2,"amount":2400000}'
curl -s -X POST localhost:8082/api/orders/1/pay -H 'Content-Type: application/json' \
  -d '{"method":"CARD"}'

# payment-service gọi trực tiếp
curl -s -X POST localhost:8083/api/payments -H 'Content-Type: application/json' \
  -d '{"orderId":1,"amount":2400000,"method":"CARD"}'
```

Các tình huống thanh toán (dùng để tạo log các mức khác nhau):

| Request | Kết quả | Log |
|---|---|---|
| `method: CARD`, `amount <= 50.000.000` | `APPROVED` | INFO |
| `amount > 50.000.000` | `DECLINED` | WARN |
| `method: FOO` (không hỗ trợ) | 400 | WARN |
| `method: BROKEN_GATEWAY` | 502 | ERROR kèm stack trace |

Log DEBUG của `com.storex.payment` nhiều và chi tiết (validate, fraud check, gọi gateway) nhưng mặc định không hiện vì payment-service chạy ở mức INFO.

## Log và index

`logstash/pipeline/logstash.conf` dùng `codec => json_lines` và tách index theo `app_name`:
`user-service-YYYY.MM.dd`, `order-service-YYYY.MM.dd`, `payment-service-YYYY.MM.dd`.

```bash
curl -s 'localhost:9200/_cat/indices?v'
```

## Actuator (payment-service)

`payment-service` có Spring Boot Actuator, đã expose `health,info,loggers`. Đổi level log lúc đang chạy:

```bash
curl -i -X POST localhost:8083/actuator/loggers/com.storex.payment \
  -H 'Content-Type: application/json' -d '{"configuredLevel":"DEBUG"}'
```

## Checkout và TraceId (RequestId)

`POST /api/checkout` chạy cả luồng mua hàng: kiểm tra giỏ hàng, giữ hàng, tạo đơn (gọi user-service), thanh toán (gọi payment-service). Các dòng log của luồng này viết theo kiểu hay gặp: chỉ dòng đầu có `userId`, dòng lỗi `Transaction Failed` không mang định danh nào.

```bash
curl -s -X POST localhost:8082/api/checkout -H 'Content-Type: application/json' \
  -d '{"userId":1,"productName":"Ban phim co","quantity":1,"amount":1200000,"paymentMethod":"CARD"}'
```

Mỗi service có `RequestIdFilter` sinh một UUID cho mỗi request. Script bắn nhiều request đồng thời, in ra kết quả thật ở phía client:

```bash
python3 scripts/load_checkout.py 20
```
