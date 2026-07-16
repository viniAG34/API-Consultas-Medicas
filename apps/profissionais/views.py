from django.db.models import ProtectedError
from rest_framework import viewsets

from apps.core.exceptions import ErroRecursoProtegido

from .models import Profissional
from .serializers import ProfissionalSerializer


class ProfissionalViewSet(viewsets.ModelViewSet):
    queryset = Profissional.objects.all()
    serializer_class = ProfissionalSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as e:
            # Ponto exato onde o Django levanta a exceção nativa — convertida aqui
            # para a exceção de domínio (ver CONVENCOES-CODIGO.md, seção 4.2).
            # A tradução para 400 acontece centralizada no tratar_erro_global.
            raise ErroRecursoProtegido(
                "Este profissional possui consultas vinculadas e não pode ser removido.",
                causa_original=e,
            )
