# 事件契约模板

## 1. 事件总览

| 事件名 | 生产者 | 消费者 | 触发时机 | 幂等键 | 顺序要求 |
|--------|--------|--------|----------|--------|----------|

## 2. 事件详情

### {event_name}

- 业务含义：
- Topic/队列：
- 生产者：
- 消费者：
- 幂等键：
- 分区键：
- 重试策略：
- 死信策略：
- 版本兼容：

```json
{
  "event_id": "",
  "event_type": "",
  "occurred_at": "",
  "tenant_id": "",
  "store_id": "",
  "trace_id": "",
  "payload": {}
}
```

## 3. 餐饮常用事件

- OrderCreated
- OrderPaid
- PaymentCallbackReceived
- RefundSucceeded
- CouponRedeemed
- InventoryDeducted
- DishSoldOutChanged
- TakeoutOrderCanceled
- StoreDailyClosed
