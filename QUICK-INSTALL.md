# Snelle Installatie

Voor een snelle installatie van het Boekhoud Systeem op een schone Ubuntu 22.04 server, gebruik je één van de onderstaande methoden.

## Methode 1: Eén-Regel Installatie

Open een terminal op je Ubuntu 22.04 server en kopieer deze regel:

```bash
sudo bash -c "$(wget -qO- https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/one-command-install.sh)"
```

## Methode 2: Stap-voor-Stap Installatie 

1. Open een terminal op je Ubuntu 22.04 server
2. Download het installatiescript:

```bash
wget https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/ubuntu-setup.sh
```

3. Maak het script uitvoerbaar:

```bash
chmod +x ubuntu-setup.sh
```

4. Voer het script uit:

```bash
sudo ./ubuntu-setup.sh
```

5. Volg de instructies in de terminal om de installatie te voltooien.

## Na Installatie

Na succesvolle installatie:

- De applicatie is beschikbaar op `http://SERVER_IP` (of via https als je een domein hebt opgegeven)
- Login met standaard admin gegevens (zie terminal output)
- Wijzig onmiddellijk het admin wachtwoord

## Basisbeheer

```bash
# Start systeem
cd /opt/boekhoud && docker-compose up -d

# Stop systeem
cd /opt/boekhoud && docker-compose down

# Bekijk logs
cd /opt/boekhoud && docker-compose logs -f

# Update systeem
cd /opt/boekhoud && ./deploy.sh

# Backup database
cd /opt/boekhoud && ./backup-database.sh
```

## Meer Informatie

Voor volledige documentatie, zie de bestanden:
- `INSTALLATIE.md` - Gedetailleerde installatie-instructies
- `README.md` - Productoverzicht en functies
- `UBUNTU_INSTALLATIE.md` - Ubuntu-specifieke installatie instructies