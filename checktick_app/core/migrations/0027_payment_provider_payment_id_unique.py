# Generated for F14 defence-in-depth: partial unique constraint on Payment.payment_id.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_webhookevent"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=~models.Q(payment_id=""),
                fields=["payment_id"],
                name="payment_provider_payment_id_unique",
            ),
        ),
    ]
