# Docker permissies troubleshooting

Als je problemen ondervindt met Docker permissies, kan deze gids je helpen om de meest voorkomende problemen op te lossen.

## Symptomen van permissie problemen

- Foutmeldingen zoals: `Permission denied`
- Foutmeldingen zoals: `Cannot connect to the Docker daemon`
- Commando's die alleen werken met `sudo` maar niet zonder

## Oplossing 1: Toevoegen aan de Docker groep

De meest voorkomende oorzaak van permissie problemen is dat je gebruiker niet in de `docker` groep zit. Voer de volgende stappen uit:

1. Voeg je gebruiker toe aan de docker groep:

   ```bash
   sudo usermod -aG docker $USER
   ```

2. Log uit en log weer in (of herstart het systeem) om de groep wijzigingen toe te passen.

3. Controleer of je nu in de docker groep zit:

   ```bash
   groups
   ```

   Je zou `docker` in de lijst moeten zien.

## Oplossing 2: Docker daemon starten

Als Docker niet draait:

```bash
sudo systemctl start docker
sudo systemctl enable docker
```

## Oplossing 3: Eigenaar van mappen wijzigen

Als je problemen hebt met bestands- of maprechten:

```bash
# Wijzig de eigenaar van de project map naar jouw gebruiker
sudo chown -R $USER:$USER /pad/naar/project/map

# Wijzig de eigenaar van docker volumes
sudo chown -R $USER:$USER /var/lib/docker/volumes/
```

## Oplossing 4: SELinux context aanpassen

Op systemen met SELinux (zoals CentOS, Fedora, RHEL):

```bash
# Voor de project map
sudo chcon -Rt svirt_sandbox_file_t /pad/naar/project/map

# Voor volumes
sudo chcon -Rt svirt_sandbox_file_t /pad/naar/volume/map
```

## Oplossing 5: Docker socket rechten

Als er specifiek problemen zijn met de Docker socket:

```bash
sudo chmod 666 /var/run/docker.sock
```

Let op: Dit is een tijdelijke oplossing en vermindert de beveiliging. Beter is om de gebruiker toe te voegen aan de docker groep (Oplossing 1).

## Oplossing 6: Docker opnieuw installeren

Als alles mislukt, kun je Docker opnieuw installeren:

```bash
# Verwijder Docker
sudo apt purge docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Installeer Docker opnieuw
sudo apt update
sudo apt install docker.io docker-compose
```

## Containergebruiker vs hostgebruiker

Een veel voorkomend probleem is het verschil tussen de gebruiker in de container (vaak `root`) en de gebruiker op het hostsysteem.

Voor het delen van bestanden en mappen zijn er drie strategieën:

1. **Volumes gebruiken**: Docker volumes worden beheerd door Docker en hebben minder last van permissie problemen.

   ```yaml
   volumes:
     - mydata:/var/www/data
   ```

2. **User mapping**: Specificeer de gebruiker ID in je Dockerfile of docker-compose.yml.

   ```yaml
   services:
     web:
       user: "${UID}:${GID}"
   ```

   En start docker-compose met:

   ```bash
   UID=$(id -u) GID=$(id -g) docker-compose up -d
   ```

3. **Permissies in de container aanpassen**: Voeg een script toe in je container die permissies aanpast.

   ```Dockerfile
   COPY entrypoint.sh /entrypoint.sh
   RUN chmod +x /entrypoint.sh
   ENTRYPOINT ["/entrypoint.sh"]
   ```

   En in je entrypoint.sh:

   ```bash
   #!/bin/bash
   # Pas rechten aan
   chown -R www-data:www-data /var/www/html
   # Start je applicatie
   exec "$@"
   ```