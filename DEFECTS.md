fix 1:
in cart.py add_item() and remove_item do not check if the quantity is greater than zero or negative. i added a helper function that checks if a quantity is a number greater than 0 and call it inside of add_item()


fix 2:
add item does not check if adding an already present item would overflow the stock. i added the following code to check:

already_added = existing.quantity if existing else 0
if already_added + quantity > product.stock:
    print('Not enough stock')
    return False

fix 3:
in apply discount, SAVE15 can cause the amount to be less than 0. i rewrote the flat subtraction to the following maximum function to prevent it from going below zero:
max(0.0, amount - 15)

fix 4:
Discounts can stack when reapplied. i changed it so that total instead returns the subtotal with the discount applied so that the discount is only ever applied once. now apply_discount just sets the discount_code property to the associated valid string.


fix5:
Loading a cart twice can result in items being duplicated. I am asuming that when a cart is loaded when a cart is already present, that the new cart will replace the current cart. this is what typically happens when you load a save in a game or load a file, so adding all of the items to the cart doesnt seem right to me. i added the following code to clear the object before loading the items:

self.lines.clear()
self.discount_code = None
self.discounted_total = None

fix 6:
Get product takes in user input and directly applies it to the sql string. this can allow for SQL injection and is a security issue. I have replaced the sql query with the following:
try:
    row = conn.execute(
        "SELECT sku, name, price, stock FROM products WHERE sku = ?",
        (sku,),
    ).fetchone()
    return Product(*row) if row else None
finally:
    conn.close()
this better protects against injection by using the SKU. its placed inside of a try/final so that the connection is closed even if the query raises an error.

fix 7:
get_saved_cart is also vulnerable to SQL injection. i've replaced the execute string with a parameter query similar to fix 6. it is also inside of a try/final so that the connection will always close.

fix 8:
list_orders does not use its user_id parameter. I changed the rows to the following
rows = conn.execute(
    "SELECT id, user_id, amount, status FROM orders "
    "WHERE user_id = ? ORDER BY id DESC",
    (user_id,),
).fetchall()


fix 9:
in CheckoutServices checkout function there is the following line of code:
        print(f'Charging payment token: {payment_token}')
this prints out the payment token, which is a security concern as it exposes potentiall yunsafe details of the user. i have removed said line of code from the function



Running the tests:
after running the tests i got 5 failures and 17 passes. i have aditional tests for checkout behavoir, checking stock again at checkout, and preventing duplicate requests that i do not have fixes for.

the following fixes are connected to the following tests:
fix 1: test_add_item_rejects_nonpositive_quantity, test_remove_item_rejects_negative_quantity
fix 2: test_duplicate_additions_cannot_exceed_available_stock
fix 3: total	test_fixed_discount_never_makes_total_negative
fix 4: test_cart_edit_recalculates_an_applied_discount,
fix 5: test_loading_the_same_saved_cart_twice_does_not_duplicate_lines
fix 6 and fix 7: test_product_lookup_treats_sku_as_data_not_sql, test_saved_cart_lookup_only_returns_the_requested_user
fix 8: test_list_orders_filters_by_user
fix 9: test_checkout_does_not_print_payment_token

AI acknowledgment:
I used chatgpt to double check my work and find resources on how to make python tests. 