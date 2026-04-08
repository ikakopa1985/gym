from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()

router.register(r"trainers", TrainerViewSet, basename="trainer")
router.register(r"memberships", MembershipViewSet, basename="membership")
router.register(r"clients", ClientViewSet, basename="client")
# router.register(r"client-memberships", ClientMembershipViewSet, basename="client-membership")
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"checkins", CheckInViewSet, basename="checkin")
router.register(r"reports", ReportsViewSet, basename="reports")
router.register(r"card-payments", CardPaymentViewSet, basename="card-payment")


urlpatterns = [
    path("", index, name="index"),
    path("clients/", clients_page, name="clients_page"),
    path("trainers/", trainers_page, name="trainers_page"),
    path("memberships/", memberships_page, name="memberships_page"),
    path("payments/", payments_page, name="payments_page"),
    path("checkins/", checkins_page, name="checkins_page"),
    path("reports/", reports_page, name="reports_page"),
    path("doorOpen/", OpenDoor, name="OpenDoor"),
    path("sync/", sync, name="sync"),
    path("syncpartial/", syncpartial, name="syncpartial"),
    path("sync/status/", sync_status),
    path("card-payments/", card_payments_page, name="card_payments"),

    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),



    path("zk/start/", zk_start),
    path("zk/stop/", zk_stop),
    path("zk/imitate/", zk_imitate),




    # API endpoints:
    path("api/", include(router.urls)),
]
