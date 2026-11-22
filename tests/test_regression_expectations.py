import pytest

from cart import ShoppingCart
from checkout import CheckoutService
from models import CartLine
from payments import FakePaymentGateway
from repository import StoreRepository
from setup_db import initialize


@pytest.fixture
def repository(tmp_path):
    db_path = tmp_path / "shop.db"
    initialize(str(db_path))
    return StoreRepository(str(db_path))


@pytest.fixture
def cart(repository):
    return ShoppingCart("student", repository)


def test_add_valid_item_updates_subtotal(cart):
    assert cart.add_item("USB-01", 2) is True
    assert cart.subtotal() == pytest.approx(19.98)


@pytest.mark.parametrize("quantity", [0, -1])
def test_add_item_rejects_nonpositive_quantity(cart, quantity):
    assert cart.add_item("USB-01", quantity) is False
    assert cart.lines == []


def test_duplicate_additions_cannot_exceed_available_stock(cart):
    assert cart.add_item("USB-01", 30) is True
    assert cart.add_item("USB-01", 21) is False
    assert cart.lines[0].quantity == 30


def test_remove_item_rejects_negative_quantity(cart):
    cart.add_item("USB-01", 3)
    assert cart.remove_item("USB-01", -2) is False
    assert cart.lines[0].quantity == 3


def test_partial_remove_updates_quantity_and_subtotal(cart):
    cart.add_item("USB-01", 3)
    assert cart.remove_item("USB-01", 1) is True
    assert cart.lines[0].quantity == 2
    assert cart.subtotal() == pytest.approx(19.98)


def test_percentage_discount_uses_cart_subtotal(cart):
    cart.add_item("MOU-01", 2)
    assert cart.apply_discount("WELCOME10") is True
    assert cart.total() == pytest.approx(53.91)


def test_fixed_discount_never_makes_total_negative(cart):
    cart.add_item("USB-01", 1)
    assert cart.apply_discount("SAVE15") is True
    assert cart.total() == pytest.approx(0)


def test_cart_edit_recalculates_an_applied_discount(cart):
    cart.add_item("MOU-01", 2)
    cart.apply_discount("WELCOME10")
    cart.add_item("USB-01", 1)
    assert cart.total() == pytest.approx((59.90 + 9.99) * 0.9)


def test_reapplying_same_coupon_does_not_stack_it(cart):
    cart.add_item("USB-01", 10)
    cart.apply_discount("WELCOME10")
    cart.apply_discount("WELCOME10")
    assert cart.total() == pytest.approx(89.91)


def test_loading_the_same_saved_cart_twice_does_not_duplicate_lines(repository):
    saved = ShoppingCart("student", repository)
    saved.add_item("USB-01", 2)
    saved.save()

    loaded = ShoppingCart("student", repository)
    loaded.load()
    first_total = loaded.subtotal()
    loaded.load()

    assert len(loaded.lines) == 1
    assert loaded.lines[0].quantity == 2
    assert loaded.subtotal() == pytest.approx(first_total)


def test_product_lookup_treats_sku_as_data_not_sql(repository):
    assert repository.get_product("missing' OR '1'='1") is None


def test_saved_cart_lookup_only_returns_the_requested_user(repository):
    repository.save_cart("student", [CartLine("USB-01", "USB cable", 9.99, 2)])
    assert repository.get_saved_cart("missing' OR '1'='1") == []


def test_list_orders_filters_by_user(repository):
    repository.save_order("student-a", 10, "paid", "request-a")
    repository.save_order("student-b", 20, "paid", "request-b")
    orders = repository.list_orders("student-a")
    assert [row[1] for row in orders] == ["student-a"]


def test_empty_checkout_does_not_call_payment_or_create_order(repository):
    gateway = FakePaymentGateway()
    result = CheckoutService(repository, gateway).checkout(
        ShoppingCart("student", repository), "TEST_TOKEN", "request-empty"
    )
    assert result.status == "empty"
    assert gateway.calls == []
    assert repository.list_orders("student") == []


def test_declined_payment_preserves_stock_and_cart(repository):
    cart = ShoppingCart("student", repository)
    cart.add_item("USB-01", 2)
    gateway = FakePaymentGateway(should_approve=False)
    starting_stock = repository.get_product("USB-01").stock

    result = CheckoutService(repository, gateway).checkout(
        cart, "TEST_TOKEN", "request-declined"
    )

    assert result.status == "declined"
    assert repository.get_product("USB-01").stock == starting_stock
    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 2


def test_payment_exception_preserves_stock_and_cart(repository):
    class FailingGateway:
        def charge(self, amount, payment_token):
            raise RuntimeError("simulated gateway failure")

    cart = ShoppingCart("student", repository)
    cart.add_item("USB-01", 2)
    starting_stock = repository.get_product("USB-01").stock

    result = CheckoutService(repository, FailingGateway()).checkout(
        cart, "TEST_TOKEN", "request-error"
    )

    assert result.status == "payment_error"
    assert repository.get_product("USB-01").stock == starting_stock
    assert len(cart.lines) == 1


def test_checkout_rechecks_stock_before_charging(repository):
    cart = ShoppingCart("student", repository)
    cart.add_item("USB-01", 2)
    repository.update_stock("USB-01", 49)  # Simulate another purchase; one remains.
    gateway = FakePaymentGateway()

    result = CheckoutService(repository, gateway).checkout(
        cart, "TEST_TOKEN", "request-out-of-stock"
    )

    assert result.status != "paid"
    assert gateway.calls == []
    assert repository.get_product("USB-01").stock == 1
    assert len(cart.lines) == 1


def test_checkout_does_not_print_payment_token(repository, capsys):
    cart = ShoppingCart("student", repository)
    cart.add_item("USB-01", 1)

    CheckoutService(repository, FakePaymentGateway()).checkout(
        cart, "SECRET_TEST_TOKEN", "request-private"
    )

    assert "SECRET_TEST_TOKEN" not in capsys.readouterr().out


def test_repeated_request_id_does_not_charge_or_create_a_second_order(repository):
    cart = ShoppingCart("student", repository)
    cart.add_item("USB-01", 1)
    gateway = FakePaymentGateway()
    service = CheckoutService(repository, gateway)

    first = service.checkout(cart, "TEST_TOKEN", "request-once")
    cart.add_item("USB-01", 1)
    second = service.checkout(cart, "TEST_TOKEN", "request-once")

    assert second.order_id == first.order_id
    assert len(gateway.calls) == 1
    assert len(repository.list_orders("student")) == 1
