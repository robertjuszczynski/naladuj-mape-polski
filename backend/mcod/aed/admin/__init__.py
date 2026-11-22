from mcod.aed.admin.acquisition import AedSourceAdmin, ConsentRequestAdmin
from mcod.aed.admin.record import AedRecordAdmin
from mcod.aed.admin.register import AggregatedAedInfoAdmin
from mcod.aed.admin.tasks import AedTaskAdmin
from mcod.aed.admin.territory import AedLeadAdmin
from mcod.aed.admin.upload import AedUploadAdmin

__all__ = [
    "AedLeadAdmin",
    "AedRecordAdmin",
    "AedSourceAdmin",
    "AggregatedAedInfoAdmin",
    "AedTaskAdmin",
    "AedUploadAdmin",
    "ConsentRequestAdmin",
]
