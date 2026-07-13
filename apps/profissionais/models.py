from django.db import models


class Profissional(models.Model):
    nome_social = models.CharField(max_length=255)
    profissao = models.CharField(max_length=100)
    registro_profissional = models.CharField(max_length=50)

    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)

    logradouro = models.CharField(max_length=255)
    numero = models.CharField(max_length=20, blank=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    cep = models.CharField(max_length=9)
    complemento = models.CharField(max_length=255, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome_social"]

    def __str__(self):
        return self.nome_social
