/**
 * Language Switcher functionality with flag animations
 * Provides a one-click language switcher with animated flag effects
 */
document.addEventListener('DOMContentLoaded', function() {
  // Get elements
  const languageSwitcher = document.querySelector('.language-switcher');
  const languageSwitcherDropdown = document.querySelector('.language-switcher-dropdown');
  const languageItems = document.querySelectorAll('.language-switcher-item');
  const currentFlag = document.querySelector('.language-switcher-current .flag-icon');
  
  if (!languageSwitcher) return;
  
  // Toggle dropdown on click
  languageSwitcher.addEventListener('click', function(e) {
    e.stopPropagation();
    languageSwitcherDropdown.classList.toggle('show');
    
    // Add wave animation to current flag
    if (currentFlag) {
      currentFlag.classList.add('flag-wave');
      
      // Remove animation class after it completes
      setTimeout(() => {
        currentFlag.classList.remove('flag-wave');
      }, 2500);
    }
  });
  
  // Close dropdown when clicking outside
  document.addEventListener('click', function() {
    languageSwitcherDropdown.classList.remove('show');
  });
  
  // Prevent dropdown from closing when clicking inside it
  languageSwitcherDropdown.addEventListener('click', function(e) {
    e.stopPropagation();
  });
  
  // Handle language selection
  languageItems.forEach(item => {
    item.addEventListener('click', function(e) {
      e.preventDefault();
      
      const languageCode = this.getAttribute('data-language');
      const flagIcon = this.querySelector('.flag-icon');
      
      // Add bounce animation to selected flag
      if (flagIcon) {
        flagIcon.classList.add('flag-bounce');
        
        // Remove animation class after it completes
        setTimeout(() => {
          flagIcon.classList.remove('flag-bounce');
          
          // Redirect to change language
          window.location.href = `/set-language/${languageCode}`;
        }, 1000);
      } else {
        // Fallback if no flag icon found
        window.location.href = `/set-language/${languageCode}`;
      }
    });
  });
});