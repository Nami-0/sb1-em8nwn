// Country data organized by continent
const countryData = {
    asia: [
        ['bangladesh', 'Bangladesh'],
        ['china', 'China'],
        ['india', 'India'],
        ['indonesia', 'Indonesia'],
        ['japan', 'Japan'],
        ['south_korea', 'South Korea'],
        ['thailand', 'Thailand'],
        ['vietnam', 'Vietnam'],
        // Add more Asian countries
    ],
    europe: [
        ['france', 'France'],
        ['germany', 'Germany'],
        ['italy', 'Italy'],
        ['spain', 'Spain'],
        ['united_kingdom', 'United Kingdom'],
        // Add more European countries
    ],
    north_america: [
        ['canada', 'Canada'],
        ['mexico', 'Mexico'],
        ['united_states', 'United States'],
        // Add more North American countries
    ],
    south_america: [
        ['argentina', 'Argentina'],
        ['brazil', 'Brazil'],
        ['chile', 'Chile'],
        ['peru', 'Peru'],
        // Add more South American countries
    ],
    africa: [
        ['egypt', 'Egypt'],
        ['kenya', 'Kenya'],
        ['morocco', 'Morocco'],
        ['south_africa', 'South Africa'],
        // Add more African countries
    ],
    oceania: [
        ['australia', 'Australia'],
        ['new_zealand', 'New Zealand'],
        ['fiji', 'Fiji'],
        // Add more Oceanian countries
    ]
};

document.addEventListener('DOMContentLoaded', function() {
    const continentSelect = document.getElementById('continent');
    const destinationSelect = document.getElementById('destination');

    // Function to update country options based on selected continent
    function updateCountries() {
        const selectedContinent = continentSelect.value;
        const countries = countryData[selectedContinent] || [];

        // Clear existing options
        destinationSelect.innerHTML = '';

        // Add default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Select a country';
        defaultOption.selected = true;
        defaultOption.disabled = true;
        destinationSelect.appendChild(defaultOption);

        // Add country options
        countries.forEach(([value, label]) => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = label;
            destinationSelect.appendChild(option);
        });
    }

    // Update countries when continent selection changes
    if (continentSelect) {
        continentSelect.addEventListener('change', updateCountries);
        // Initial population of countries
        updateCountries();
    }
});
