# How the matching works (explained like you're 5)

Imagine you have a toy in your hand, and you want to know if two other toy shops sell **the very same toy**.
Not a toy that looks a bit like it. The *same* one.

That's what this app does. The toy is a product on Amazon. The other shops are Flipkart, Croma and Myntra.

---

## Step 1: Look closely at the toy

First we read the Amazon page and write down the important things about the product, like a little name tag:

> **Samsung · Galaxy S25 Ultra · 12 GB RAM · 256 GB**

We throw away the "shouting words" sellers add to sound exciting: *AI*, *Smart*, *5G*, *Premium*, *Stylish*, *New*.
They don't tell us *which* toy it is. They're just decoration.

## Step 2: Go to the right shops

Different shops sell different things, so we only ask the shops that make sense:

| What it is | Shops we ask |
|---|---|
| 📱 Phone | Flipkart, Croma |
| 📺 TV | Flipkart, Croma |
| 👟 Sneakers | Flipkart, Myntra |
| 👕 T-shirt, polo, jersey | Flipkart, Myntra |

If it's something else (a phone cover, headphones, a kurta, slippers), we say *"sorry, I only know these four kinds of things"*.

## Step 3: Check the name tag, every single time

For every product a shop shows us, we ask two questions.

**Question 1: Same brand and same model?** This one is always asked.

- *Samsung Galaxy S24* and *Samsung Galaxy S24 FE* are **different**. "FE" is a different toy, even though it sounds almost the same.
- *iPhone 15* and *iPhone 16* are **different**. A different number means a different toy.
- *Nike Court Royale* and *Nike Court Royale **2*** are **different**, for the same reason.
- *TCL 55Q6C* and *TCL 55Q6C**S*** are **different**. One extra letter at the end of a model code is a different TV.

**Question 2: The special rule for that kind of thing.**

| Kind | It must also match… | Example of a "no" |
|---|---|---|
| 📱 Phone | RAM **and** storage | OnePlus with 16 GB RAM ≠ the same OnePlus with 12 GB RAM |
| 📺 TV | Screen size | A 43-inch TV ≠ the 55-inch one, even with the same name |
| 👟 Sneakers | Colour | White Sparx ≠ black Sparx |
| 👕 T-shirts | Colour | A navy polo ≠ the olive one |

Only when **both** answers are "yes" do we say it's the same product.

Colours have many names, so we group them into families:
*Navy*, *Midnight* and *Cobalt* all count as **blue**, and *Onyx* and *Jet* count as **black**.

## Step 4: Tell you what we found

Each shop gets one of three answers, and each one looks different on the screen:

- 🟢 **In stock**: they have the same product and you can buy it. We give you the link.
- 🟠 **Out of stock**: they have the same product but it's sold out right now. We still give you the link.
- ⚪ **Not listed**: they don't sell this exact product.

When a shop has the right model but in the **wrong** RAM, size or colour, we say so and link those too:
*"Found this model, but only with 16 GB RAM / 512 GB."* That's still "not listed", because it's not the same toy.

If a shop is broken or blocks us, we say **"Couldn't check"**. We never pretend that means "not listed".

## Step 5: When we're not sure, we say so

Sometimes Amazon doesn't tell us which toy it is. *"Levi's Men T-Shirt, Green"* could be any of a hundred green Levi's T-shirts.
Guessing would mean showing you the **wrong** shirt, so we say:

> *"Amazon doesn't name a model for this product, so it can't be matched reliably."*

**Saying "I don't know" is better than being confidently wrong.**

---

## The tricky ones we learned from

We tried 100+ real products. These are the mistakes we caught and fixed:

| Looked the same… | …but wasn't | What we taught the app |
|---|---|---|
| Bewakoof *Batman* tee | A *Riddler* print, also called "Batman" | One word isn't enough to tell T-shirt designs apart |
| Sony *K-55S25**BM2*** | Sony *K-55S25*, last year's TV | An extra number at the end means a newer model |
| ASICS Gel-Quantum *Lyte **II*** | Gel-Quantum *Kei* | "II" means 2, a version number |
| Campus OG-27 white/**green** | OG-27 white/**black** | If both shops name the full colour mix, the accent colour must match too |
| Bata "lace-up sneaker" | A formal Derby shoe | Formal shoes aren't sneakers |
| Redmi Note 15 *Pro+* | Flipkart writes "Pro **+**" with a space | "Pro +" and "Pro+" are the same thing |
| vivo T5x: the title said 8 GB | Amazon's spec table said 6 GB | When they disagree, trust the title |

## What it can't do (yet)

- **Croma:** we can see that Croma *lists* a product, but its live stock and today's price only show in a real browser. So Croma shows its listed price, and we say so on the card.
- **Sizes:** "in stock" means some size is in stock, not necessarily yours.
- **Plain T-shirts:** most plain or generic tees on Amazon have no model name, so they show "can't be matched reliably" instead of a guess.
- **Hidden colours:** Myntra sometimes hides other colours behind a "More colors" button, so a colour can be missed.
