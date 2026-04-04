from django.db import migrations


def update_role_names(apps, schema_editor):
    User = apps.get_model("accounts", "User")

    # Old -> New
    User.objects.filter(role="ORG_OWNER").update(role="OWNER")
    User.objects.filter(role="ORG_ADMIN").update(role="ADMIN")


def reverse_role_names(apps, schema_editor):
    User = apps.get_model("accounts", "User")

    # New -> Old (so migration is reversible)
    User.objects.filter(role="OWNER").update(role="ORG_OWNER")
    User.objects.filter(role="ADMIN").update(role="ORG_ADMIN")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_birth_date_alter_organization_org_id"),
    ]

    operations = [
        migrations.RunPython(update_role_names, reverse_role_names),
    ]
