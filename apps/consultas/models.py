from django.db import models


class Consulta(models.Model):
    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.PROTECT,
        related_name="consultas",
    )
    data_hora = models.DateTimeField(db_index=True)  # índice — ver RN-12

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_hora"]
        constraints = [
            models.UniqueConstraint(
                fields=["profissional", "data_hora"],
                name="uniq_profissional_data_hora",  # RN-12 — detalhado no SDD-03
            )
        ]

    def __str__(self):
        return f"{self.profissional.nome_social} — {self.data_hora}"
