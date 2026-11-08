package com.storex.order.service;

import com.storex.order.client.PaymentClient;
import com.storex.order.dto.CheckoutRequest;
import com.storex.order.dto.CreateOrderRequest;
import com.storex.order.dto.PaymentResponse;
import com.storex.order.entity.StoreOrder;
import com.storex.order.repository.StoreOrderRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

import java.util.concurrent.ThreadLocalRandom;

/**
 * Luong mua hang: kiem tra gio hang, giu hang, tao don, thanh toan.
 * Cac dong log o day duoc viet theo kieu hay gap trong thuc te: chi dong dau co userId,
 * cac dong sau (dac biet la dong loi) khong mang theo dinh danh nao.
 */
@Service
public class CheckoutService {

    private static final Logger log = LoggerFactory.getLogger(CheckoutService.class);

    private final OrderService orderService;
    private final PaymentClient paymentClient;
    private final StoreOrderRepository orderRepository;

    public CheckoutService(OrderService orderService,
                           PaymentClient paymentClient,
                           StoreOrderRepository orderRepository) {
        this.orderService = orderService;
        this.paymentClient = paymentClient;
        this.orderRepository = orderRepository;
    }

    public StoreOrder checkout(CheckoutRequest request) {
        log.info("Checkout started userId={}", request.userId());

        log.debug("Validating cart items");
        simulateWork();
        log.debug("Reserving stock");
        simulateWork();

        StoreOrder order = orderService.createOrder(new CreateOrderRequest(
                request.userId(), request.productName(), request.quantity(), request.amount()));

        log.debug("Charging payment");
        simulateWork();

        PaymentResponse response;
        try {
            response = paymentClient.pay(order.getId(), order.getAmount(), request.paymentMethod());
        } catch (RestClientException e) {
            markOrder(order, "PAYMENT_FAILED");
            log.error("Transaction Failed", e);
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "Payment service error");
        }

        if (!"APPROVED".equals(response.status())) {
            markOrder(order, "PAYMENT_DECLINED");
            log.error("Transaction Failed: payment declined");
            throw new ResponseStatusException(HttpStatus.PAYMENT_REQUIRED, "Payment declined");
        }

        markOrder(order, "PAID");
        log.info("Checkout completed");
        return order;
    }

    private void markOrder(StoreOrder order, String status) {
        order.setStatus(status);
        orderRepository.save(order);
    }

    /** Mo phong thoi gian xu ly de cac request chong lan nhau khi chay dong thoi. */
    private void simulateWork() {
        try {
            Thread.sleep(ThreadLocalRandom.current().nextLong(20, 120));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
