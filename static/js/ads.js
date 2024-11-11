// Initialize ad containers when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Function to check if an element is in viewport
    function isInViewport(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }

    // Initialize all ad containers
    function initAds() {
        const adContainers = document.querySelectorAll('.ad-container');
        adContainers.forEach(container => {
            if (isInViewport(container) && !container.dataset.loaded) {
                container.dataset.loaded = true;
                // Ad loading logic will be handled by AdSense
            }
        });
    }

    // Listen for scroll events to initialize ads when they come into view
    window.addEventListener('scroll', initAds);
    // Initial check for visible ads
    initAds();
});
