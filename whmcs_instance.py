"""
Module om een gedeelde singleton instantie van de WHMCS service aan te bieden.
"""
from whmcs_service import WHMCSService

# Creëer een gedeelde instantie voor hergebruik
whmcs_service = WHMCSService()