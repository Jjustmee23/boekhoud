/**
 * Onboarding Tutorial voor Facturatie & Boekhouding
 * Dit script initialiseert en beheert de interactieve onboarding ervaring
 * voor nieuwe gebruikers van het systeem.
 */

class OnboardingTutorial {
  constructor() {
    // Initialiseer Shepherd.js tour instantie
    this.tour = null;
    this.userRole = document.body.getAttribute('data-user-role') || 'user';
    this.isNewUser = document.body.getAttribute('data-new-user') === 'true';
    this.tutorials = {
      admin: this.createAdminTutorial,
      user: this.createUserTutorial,
      superadmin: this.createSuperAdminTutorial
    };
    
    // Wacht tot de pagina geladen is
    document.addEventListener('DOMContentLoaded', () => {
      // Laad Shepherd.js dynamisch
      this.loadShepherdJS().then(() => {
        // Controleer of de gebruiker nieuw is
        if (this.isNewUser && !this.hasSeenTutorial()) {
          // Toon welkom modal
          this.showWelcomeModal();
        }
        
        // Voeg tutorial starten knop toe aan navbar
        this.addTutorialButton();
      });
    });
  }
  
  /**
   * Laad Shepherd.js dynamisch
   */
  loadShepherdJS() {
    return new Promise((resolve, reject) => {
      // Laad CSS
      const cssLink = document.createElement('link');
      cssLink.rel = 'stylesheet';
      cssLink.href = 'https://cdn.jsdelivr.net/npm/shepherd.js@10.0.1/dist/css/shepherd.css';
      document.head.appendChild(cssLink);
      
      // Laad JS
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/shepherd.js@10.0.1/dist/js/shepherd.min.js';
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }
  
  /**
   * Controleer of gebruiker de tutorial al heeft gezien
   * Combinatie van lokale opslag (voor snelheid) en server data
   */
  hasSeenTutorial() {
    const localSetting = localStorage.getItem('tutorialCompleted') === 'true';
    
    // Primair baseren we op server status (is_new_user), maar 
    // gebruiken lokale opslag voor betere gebruikerservaring
    if (localSetting) {
      return true;
    }
    
    // Indien lokale opslag niet aanwezig, gebruiken we alleen 
    // de data-new-user attributen die door de server zijn gezet
    return !this.isNewUser;
  }
  
  /**
   * Markeer tutorial als gezien (server + local storage)
   */
  markTutorialCompleted() {
    // Lokale opslag voor gebruikerservaring consistentie
    localStorage.setItem('tutorialCompleted', 'true');
    
    // Server update voor persistentie tussen apparaten
    fetch('/onboarding/complete-tutorial', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
    .then(response => response.json())
    .then(data => {
      console.log('Tutorial status bijgewerkt op server:', data);
    })
    .catch(error => {
      console.error('Fout bij het bijwerken van tutorial status:', error);
    });
  }
  
  /**
   * Reset tutorial status (server + local storage)
   */
  resetTutorialStatus() {
    // Lokale opslag resetten
    localStorage.removeItem('tutorialCompleted');
    
    // Server reset voor persistentie tussen apparaten
    fetch('/onboarding/reset', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
    .then(response => response.json())
    .then(data => {
      console.log('Tutorial status gereset op server:', data);
    })
    .catch(error => {
      console.error('Fout bij het resetten van tutorial status:', error);
    });
  }
  
  /**
   * Toon een welkomstscherm voor nieuwe gebruikers
   */
  showWelcomeModal() {
    const modal = document.createElement('div');
    modal.className = 'onboarding-modal';
    modal.innerHTML = `
      <div class="onboarding-modal-content">
        <h2 class="onboarding-welcome-title">Welkom bij Facturatie & Boekhouding!</h2>
        <p class="onboarding-welcome-text">
          We hebben een korte rondleiding voor je voorbereid om je te helpen
          vertrouwd te raken met het systeem. Je leert de basisfuncties kennen
          en kunt daarna direct aan de slag.
        </p>
        <button class="onboarding-welcome-button">Start Rondleiding</button>
        <div class="onboarding-dismiss">Nu niet, later herinneren</div>
      </div>
    `;
    document.body.appendChild(modal);
    
    // Voeg animatie toe
    setTimeout(() => modal.classList.add('show'), 100);
    
    // Event handlers
    modal.querySelector('.onboarding-welcome-button').addEventListener('click', () => {
      modal.classList.remove('show');
      setTimeout(() => {
        modal.remove();
        this.startTutorial();
      }, 300);
    });
    
    modal.querySelector('.onboarding-dismiss').addEventListener('click', () => {
      modal.classList.remove('show');
      setTimeout(() => modal.remove(), 300);
    });
  }
  
  /**
   * Voeg een tutorial knop toe aan de navigatiebalk
   */
  addTutorialButton() {
    const navbar = document.querySelector('.navbar-nav');
    if (!navbar) return;
    
    const listItem = document.createElement('li');
    listItem.className = 'nav-item';
    listItem.innerHTML = `
      <a class="nav-link" href="#" id="start-tutorial">
        <i class="fas fa-question-circle"></i> Rondleiding
      </a>
    `;
    
    navbar.appendChild(listItem);
    
    document.getElementById('start-tutorial').addEventListener('click', (e) => {
      e.preventDefault();
      this.startTutorial();
    });
  }
  
  /**
   * Start de tutorial voor de huidige gebruiker
   */
  startTutorial() {
    // Reset eerder tour als die bestaat
    if (this.tour) {
      this.tour.complete();
    }
    
    // Maak Shepherd tour instantie
    this.tour = new Shepherd.Tour({
      useModalOverlay: true,
      defaultStepOptions: {
        classes: 'shepherd-theme-arrows',
        scrollTo: true,
        cancelIcon: {
          enabled: true
        }
      }
    });
    
    // Haal de juiste tutorial voor gebruikersrol
    const createTutorialSteps = this.tutorials[this.userRole] || this.tutorials.user;
    createTutorialSteps.call(this);
    
    // Start de tour
    this.tour.start();
  }
  
  /**
   * Tutorial voor reguliere gebruikers
   */
  createUserTutorial() {
    // Dashboard intro
    this.tour.addStep({
      id: 'dashboard-intro',
      title: 'Welkom bij het Dashboard',
      text: 'Dit is je dashboard, waar je een overzicht ziet van je facturen, klanten en financiële gegevens.',
      attachTo: {
        element: '.container h1',
        on: 'bottom'
      },
      buttons: [
        {
          text: 'Overslaan',
          action: this.tour.complete
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
    
    // Navigatie uitleg
    this.tour.addStep({
      id: 'navigation',
      title: 'Navigatie',
      text: 'Via deze menubalk kun je navigeren naar verschillende onderdelen van het systeem.',
      attachTo: {
        element: '.navbar',
        on: 'bottom'
      },
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
    
    // Facturen sectie
    this.tour.addStep({
      id: 'invoices',
      title: 'Facturen',
      text: 'Hier kun je je facturen beheren. Klik op deze link om naar de facturenpagina te gaan.',
      attachTo: {
        element: 'a[href*="invoices"]',
        on: 'right'
      },
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
    
    // Klanten sectie
    this.tour.addStep({
      id: 'customers',
      title: 'Klanten',
      text: 'Beheer hier je klantenbestand. Je kunt klanten toevoegen, wijzigen en verwijderen.',
      attachTo: {
        element: 'a[href*="customers"]',
        on: 'right'
      },
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
    
    // Rapporten sectie
    this.tour.addStep({
      id: 'reports',
      title: 'Rapporten',
      text: 'Hier vind je verschillende financiële rapporten en analyses van je bedrijfsgegevens.',
      attachTo: {
        element: 'a[href*="reports"]',
        on: 'right'
      },
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
    
    // BTW-aangifte
    this.tour.addStep({
      id: 'vat-report',
      title: 'BTW-aangifte',
      text: 'Bereid hier je BTW-aangifte voor en exporteer de gegevens voor de Belastingdienst.',
      attachTo: {
        element: 'a[href*="vat-report"]',
        on: 'right'
      },
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
    
    // Gebruikersmenu
    this.tour.addStep({
      id: 'user-menu',
      title: 'Gebruikersmenu',
      text: 'Via dit menu kun je je profiel beheren, instellingen wijzigen en uitloggen.',
      attachTo: {
        element: '#navbarDropdown',
        on: 'bottom'
      },
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
    
    // Afsluiting
    this.tour.addStep({
      id: 'conclusion',
      title: 'Klaar om te beginnen!',
      text: 'Je bent nu bekend met de basisfuncties van het systeem. Heb je nog vragen? Klik dan op de "Rondleiding" knop in de navigatiebalk om deze uitleg opnieuw te bekijken.',
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Afronden',
          action: () => {
            this.markTutorialCompleted();
            this.tour.complete();
          }
        }
      ]
    });
  }
  
  /**
   * Tutorial voor beheerders
   */
  createAdminTutorial() {
    // Start met de gebruikerstutorial
    this.createUserTutorial();
    
    // Voeg admin-specifieke stappen toe voor het einde
    this.tour.addStep({
      id: 'admin-dashboard',
      title: 'Beheerdersdashboard',
      text: 'Als beheerder heb je toegang tot extra functies. Via het beheerdersdashboard kun je gebruikers, werkruimten en abonnementen beheren.',
      attachTo: {
        element: 'a[href*="admin"]',
        on: 'bottom'
      },
      before: 'conclusion',
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
    
    // Werkruimte beheer
    this.tour.addStep({
      id: 'workspace-management',
      title: 'Werkruimtebeheer',
      text: 'Hier kun je je werkruimte configureren, gebruikers uitnodigen en hun rechten beheren.',
      attachTo: {
        element: '.navbar',
        on: 'bottom'
      },
      before: 'conclusion',
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
  }
  
  /**
   * Tutorial voor super admins
   */
  createSuperAdminTutorial() {
    // Start met de admin tutorial
    this.createAdminTutorial();
    
    // Voeg super-admin-specifieke stappen toe voor het einde
    this.tour.addStep({
      id: 'super-admin-features',
      title: 'Super Admin Functies',
      text: 'Als super admin kun je alle werkruimten beheren en tussen werkruimten schakelen via dit menu.',
      attachTo: {
        element: '#workspaceDropdown',
        on: 'bottom'
      },
      before: 'conclusion',
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
    
    // Systeem instellingen
    this.tour.addStep({
      id: 'system-settings',
      title: 'Systeeminstellingen',
      text: 'Hier kun je globale systeeminstellingen configureren, zoals e-mailintegraties, betalingsgateways en andere geavanceerde opties.',
      attachTo: {
        element: 'a[href*="system"]',
        on: 'right'
      },
      before: 'conclusion',
      buttons: [
        {
          text: 'Vorige',
          action: this.tour.back
        },
        {
          text: 'Volgende',
          action: this.tour.next
        }
      ]
    });
  }
}

// Instantieer de onboarding tutorial
const onboarding = new OnboardingTutorial();

// Voeg een globale functie toe om de tutorial te starten
window.startTutorial = function() {
  onboarding.startTutorial();
};

// Voeg een globale functie toe om de tutorial status te resetten
window.resetTutorial = function() {
  onboarding.resetTutorialStatus();
  alert('Tutorial status gereset. Ververs de pagina om de welkomstmelding opnieuw te zien.');
};