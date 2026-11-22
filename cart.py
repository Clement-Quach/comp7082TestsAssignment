"""Business logic. Several design and correctness issues are intentional."""
from models import CartLine


class ShoppingCart:
    def __init__(self, user_id, repository):
        self.user_id = user_id
        self.repository = repository
        self.lines = []
        self.discount_code = None
        self.discounted_total = None

    def add_item(self, sku, quantity):
        product = self.repository.get_product(sku)
        if not self.valid_quantity(quantity):
            print('Invalid quantity')
            return False
        if not product:
            print('Unknown product')
            return False
        if product.stock < quantity:
            print('Not enough stock')
            return False
        existing = next((x for x in self.lines if x.sku == sku), None)
        already_added = existing.quantity if existing else 0
        if already_added + quantity > product.stock:
            print('Not enough stock')
            return False
        if existing:
            existing.quantity += quantity
        else:
            self.lines.append(CartLine(sku, product.name, product.price, quantity))
        return True

    def remove_item(self, sku, quantity=None):
        if not self.valid_quantity(quantity) and quantity is not None:
            print('Invalid quantity')
            return False
        for line in self.lines:
            if line.sku == sku:
                if quantity is None or quantity >= line.quantity:
                    self.lines.remove(line)
                else:
                    line.quantity -= quantity
                return True
        print('Item not found')
        return False

    def subtotal(self):
        return sum(line.unit_price * line.quantity for line in self.lines)

    def total(self):
        subtotal = self.subtotal()

        if self.discount_code == "WELCOME10":
            return round(subtotal * 0.90, 2)
        if self.discount_code == "STUDENT20":
            return round(subtotal * 0.80, 2)
        if self.discount_code == "SAVE15":
            return round(max(0.0, subtotal - 15), 2)
        if self.discount_code == "FREESHIP":
            #free shipping makes no changes
            print('Free shipping applied') 
        return round(subtotal, 2)


    def apply_discount(self, code):
        valid_codes = {"WELCOME10", "STUDENT20", "SAVE15", "FREESHIP"}
        if code not in valid_codes:
            return False

        self.discount_code = code
        return True

    def load(self):
        self.lines.clear()
        self.discount_code = None
        self.discounted_total = None
        for sku, quantity in self.repository.get_saved_cart(self.user_id):
            self.add_item(sku, quantity)

    def save(self):
        self.repository.save_cart(self.user_id, self.lines)
    
    def valid_quantity(self, quantity):
        return (
            isinstance(quantity, int)
            and not isinstance(quantity, bool)
            and quantity > 0
        )
