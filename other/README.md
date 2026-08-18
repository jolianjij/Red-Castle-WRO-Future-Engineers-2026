# other — documentation

**Start here:** [`start-here.html`](start-here.html) — the hub. Which document
answers which question, the five commands you actually use, and where the
project stands.

| file | what it answers |
|---|---|
| [`start-here.html`](start-here.html) | *Where do I even begin?* |
| [`system-reference.html`](system-reference.html) | *How does the car actually work?* |
| [`tunables.html`](tunables.html) | *It is misbehaving — what do I change?* |
| [`api-reference.html`](api-reference.html) | *What can I call in my own code?* |
| [`code-walkthrough.html`](code-walkthrough.html) | *Why is this line here?* |
| [`tuning-strategy.md`](tuning-strategy.md) | *What do I do at the venue, in what order?* |
| [`ssh-commands.md`](ssh-commands.md) | *How do I copy that to the Pi?* |
| [`venue-setup.md`](venue-setup.md) | *No wireless allowed — now what?* |
| [`bill-of-materials.md`](bill-of-materials.md) | what the car is made of |
| [`wro-requirements-compliance.md`](wro-requirements-compliance.md) | the rules, and where we meet them |

The four HTML documents are also published as web pages — the links are in
`start-here.html`.

## Regenerating

Three of them are generated from `src/`, so they cannot drift from the code.
**Regenerate rather than editing them by hand:**

```bash
python other/build-api-reference.py      # api-reference.html
python other/build-tunables.py           # tunables.html
python other/build-code-walkthrough.py   # code-walkthrough.html
```
