from rest_framework import viewsets

from .models import Consulta
from .serializers import ConsultaSerializer


class ConsultaViewSet(viewsets.ModelViewSet):
    serializer_class = ConsultaSerializer

    def get_queryset(self):
        queryset = Consulta.objects.select_related("profissional").all()  # RN-12

        id_profissional = self.request.query_params.get("profissional")
        if id_profissional:
            queryset = queryset.filter(profissional_id=id_profissional)

        data_inicio = self.request.query_params.get("data_inicio")
        data_fim = self.request.query_params.get("data_fim")
        if data_inicio:
            queryset = queryset.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_hora__date__lte=data_fim)

        return queryset
