pretix-signature-field
======================

A `pretix <https://pretix.eu>`_ plugin that adds a **handwritten signature**
question type to the checkout process.

Buyers can draw their signature directly in their browser using a mouse or a
touch gesture.  The signature is captured as a PNG data-URL (base64) and stored
in the standard ``QuestionAnswer`` table alongside all other question answers.

Features
--------

* New question type **"Handwritten signature"** visible in the pretix backend
  question editor.
* Responsive HTML5 canvas pad — works on desktop (mouse) and mobile (touch).
* "Clear" button to reset the canvas.
* Restores a previously saved signature when the checkout page is revisited.
* Stores the raw PNG base64 data in ``QuestionAnswer.answer`` — no extra
  database tables or migrations required.
* The backend order detail page shows ``(signature on file)`` instead of the
  raw base64 blob.
* Fully localised (English + French included).

Installation
------------

.. code-block:: bash

    pip install pretix-signature-field

Then add the plugin to your pretix configuration::

    [pretix]
    plugins=pretix_signature_field,...

Or activate it per-organiser / per-event in the pretix backend under
*Settings → Plugins*.

Usage
-----

1. Go to an event in the pretix backend.
2. Open *Questions* and create a new question.
3. Select **"Handwritten signature"** as the question type.
4. Assign the question to the relevant products.
5. Buyers will see the signature pad during checkout.

Technical notes
---------------

* The signature is validated client-side (canvas serialisation) and
  server-side (regex check that the value is a valid ``image/png`` data-URL).
* Maximum accepted data-URL size: 14 MB (≈ 10 MB uncompressed image).
* The monkey-patching of ``BaseQuestionsForm.__init__`` intercepts pretix's
  question form loop **before** it processes questions, filters out
  ``TYPE_SIGNATURE`` questions, lets the original code run, then appends the
  signature field afterwards.  The pre-fetched ``questions_to_ask`` list is
  restored after each form instantiation to avoid side-effects.

License
-------

Apache Software License 2.0 — see ``LICENSE`` for details.
