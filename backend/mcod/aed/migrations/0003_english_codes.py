from django.db import migrations, models

RECORD_STATUSES = {
    "gotowy": "ready",
    "niepelny": "incomplete",
    "do_decyzji": "needs_decision",
    "do_poprawy": "needs_fix",
    "wstrzymany": "held",
}
UPLOAD_STATUSES = {"szkic": "draft", "opublikowany": "published"}
DECISIONS = {"akceptuj": "accept", "wstrzymaj": "hold"}
SEVERITIES = {"blad": "error", "ostrzezenie": "warning"}
ISSUE_CODES = {
    "dane_osobowe": "personal_data",
    "brak_wymaganego": "missing_required",
    "zly_format": "bad_format",
    "brak_godzin": "missing_hours",
    "poza_polska": "outside_poland",
    "poza_gmina": "outside_municipality",
    "przy_granicy_gminy": "near_municipality_border",
    "duplikat_punktu": "duplicate_point",
    "zamiana_wspolrzednych": "swapped_coordinates",
}
MAPPING_TARGETS = {"_adres_w_jednej_kolumnie": "_address_in_one_column"}
DATASET_KEYS = {"aed_profil": "aed_profile", "aed_zbior_ogolnopolski": "aed_national_dataset"}
NATIONAL_FLAGS = {"tak": "true"}


def invert(mapping):
    return {new: old for old, new in mapping.items()}


def convert_issues(issues, codes, severities):
    return [
        dict(i, code=codes.get(i.get("code"), i.get("code")), severity=severities.get(i.get("severity"), i.get("severity")))
        for i in issues
    ]


def convert_fixes(fixes, codes):
    return [dict(f, rule=codes.get(f.get("rule"), f.get("rule"))) for f in fixes]


def convert_checked(row, statuses, codes, severities):
    return dict(
        row,
        status=statuses.get(row.get("status"), row.get("status")),
        issues=convert_issues(row.get("issues", []), codes, severities),
        fixes=convert_fixes(row.get("fixes", []), codes),
    )


def convert(apps, statuses, upload_statuses, decisions, severities, codes, targets, dataset_keys, flags):
    AedRecord = apps.get_model("aed", "AedRecord")
    AedUpload = apps.get_model("aed", "AedUpload")
    Dataset = apps.get_model("datasets", "Dataset")

    for record in AedRecord.objects.all().iterator():
        AedRecord.objects.filter(pk=record.pk).update(
            status=statuses.get(record.status, record.status),
            issues=convert_issues(record.issues, codes, severities),
            fixes=convert_fixes(record.fixes, codes),
        )

    for upload in AedUpload.objects.all().iterator():
        AedUpload.objects.filter(pk=upload.pk).update(
            status=upload_statuses.get(upload.status, upload.status),
            checked=[convert_checked(row, statuses, codes, severities) for row in upload.checked],
            decisions={k: decisions.get(v, v) for k, v in upload.decisions.items()},
            mapping={k: targets.get(v, v) for k, v in upload.mapping.items()},
        )

    old_keys = list(dataset_keys)
    for dataset in Dataset.objects.filter(customfields__has_any_keys=old_keys).iterator():
        custom = {}
        for key, value in dataset.customfields.items():
            new_key = dataset_keys.get(key, key)
            custom[new_key] = flags.get(value, value) if new_key != key else value
        Dataset.objects.filter(pk=dataset.pk).update(customfields=custom)


def forwards(apps, schema_editor):
    convert(
        apps,
        RECORD_STATUSES,
        UPLOAD_STATUSES,
        DECISIONS,
        SEVERITIES,
        ISSUE_CODES,
        MAPPING_TARGETS,
        DATASET_KEYS,
        NATIONAL_FLAGS,
    )


def backwards(apps, schema_editor):
    convert(
        apps,
        invert(RECORD_STATUSES),
        invert(UPLOAD_STATUSES),
        invert(DECISIONS),
        invert(SEVERITIES),
        invert(ISSUE_CODES),
        invert(MAPPING_TARGETS),
        invert(DATASET_KEYS),
        invert(NATIONAL_FLAGS),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("aed", "0002_verbose_names_and_status_choices"),
        ("datasets", "0046_auto_20260907_1051"),
    ]

    operations = [
        migrations.RenameField(model_name="aedupload", old_name="licencja", new_name="license"),
        migrations.AlterField(
            model_name="aedrecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("ready", "Gotowy"),
                    ("incomplete", "Niepełny"),
                    ("needs_decision", "Do decyzji"),
                    ("needs_fix", "Do poprawy"),
                    ("held", "Wstrzymany"),
                ],
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AlterField(
            model_name="aedupload",
            name="status",
            field=models.CharField(
                choices=[("draft", "Szkic"), ("published", "Opublikowany")],
                default="draft",
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
