#!/bin/sh
# Birinchi marta SSL sertifikat olish (Let's Encrypt, bepul).
# Ishlatish: sh deploy/get-ssl.sh
set -e

DOMAIN=$(grep -E '^DOMAIN=' .env | cut -d= -f2- | tr -d '[:space:]')
EMAIL=$(grep -E '^LETSENCRYPT_EMAIL=' .env | cut -d= -f2- | tr -d '[:space:]')

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Xato: .env faylida DOMAIN va LETSENCRYPT_EMAIL ni to'ldiring."
    exit 1
fi

echo ">>> $DOMAIN uchun sertifikat olinmoqda..."

# 80-port bo'sh bo'lishi kerak — nginx ishlayotgan bo'lsa to'xtatamiz
docker compose --profile webhook stop nginx 2>/dev/null || true

docker compose --profile webhook run --rm -p 80:80 --entrypoint certbot certbot \
    certonly --standalone -d "$DOMAIN" --email "$EMAIL" --agree-tos --no-eff-email

echo ">>> Tayyor! Endi ishga tushiring: docker compose --profile webhook up -d --build"
