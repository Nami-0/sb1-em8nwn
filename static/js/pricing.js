// pricing.js
class PricingManager {
    constructor() {
        this.billingCycle = "monthly";
        this.stripePublicKey = document.querySelector('meta[name="stripe-public-key"]')?.content;
        this.stripe = null;
        this.priceIds = {
            solo_backpacker: {
                monthly: "free",
                yearly: "free"
            },
            tandem_trekker: {
                monthly: "price_monthly_tandem_trekker",     // $4.99/month
                yearly: "price_yearly_tandem_trekker"        // $49.90/year (Save 17%)
            },
            gold_wanderer: {
                monthly: "price_monthly_gold_wanderer",      // $14.99/month
                yearly: "price_yearly_gold_wanderer"         // $149.90/year (Save 17%)
            }
        };

        // Plan feature definitions
        this.planFeatures = {
            solo_backpacker: {
                name: "Solo Backpacker",
                badge: "Free",
                limits: {
                    itineraries: 1,
                    duration: 1,
                    travelers: 1,
                    infants: 0
                },
                features: [
                    "✔️ 1 itinerary per month",
                    "✔️ 1-day trips",
                    "✔️ 1 traveler only",
                    "✔️ Basic AI Recommendation",
                    "✔️ Detail planning including:",
                    "✔️ Time & dates",
                    "✔️ Maps feature",
                    "✔️ Budget breakdown",
                    "❌ Travel Buddy access",
                    "❌ PDF export"
                ]
            },
            tandem_trekker: {
                name: "Tandem Trekkers",
                badge: "Basic",
                limits: {
                    itineraries: 3,
                    duration: 3,
                    travelers: 2,
                    infants: 2
                },
                features: [
                    "✔️ 3 itineraries per month",
                    "✔️ Up to 3-day trips",
                    "✔️ 2 travelers + 2 infants",
                    "✔️ Advanced AI Recommendation",
                    "✔️ Detail planning including:",
                    "✔️ Time & dates",
                    "✔️ Maps feature",
                    "✔️ Budget breakdown",
                    "❌ Travel Buddy access",
                    "❌ PDF export"
                ]
            },
            gold_wanderer: {
                name: "Gold Wanderer",
                badge: "Most Popular",
                limits: {
                    itineraries: 6,
                    duration: 7,
                    travelers: 10,
                    infants: 5
                },
                features: [
                    "✔️ 6 itineraries per month",
                    "✔️ Up to 7-day trips",
                    "✔️ Up to 10 travelers",
                    "✔️ Advanced AI Recommendation",
                    "✔️ Priority Support",
                    "✔️ Detail planning including:",
                    "✔️ Time & dates",
                    "✔️ Maps feature",
                    "✔️ Budget breakdown",
                    "✔️ Travel Buddy Access",
                    "✔️ PDF Export"
                ]
            }
        };

        this.init();
    }

    async init() {
        try {
            await this.initializeStripe();
            this.setupEventListeners();
            this.setupTooltips();
            this.updatePriceDisplay();
        } catch (error) {
            console.error('Initialization error:', error);
            this.showToast('Error', 'Failed to initialize pricing system', 'error');
        }
    }

    async initializeStripe() {
        if (!this.stripePublicKey) {
            console.warn('Stripe public key not found');
            return;
        }

        try {
            this.stripe = await loadStripe(this.stripePublicKey);
        } catch (error) {
            console.error('Stripe initialization failed:', error);
            throw new Error('Payment system initialization failed');
        }
    }

    setupEventListeners() {
        // Billing cycle toggle
        const billingToggle = document.getElementById('billingToggle');
        if (billingToggle) {
            billingToggle.addEventListener('change', (e) => this.handleBillingToggle(e));
        }

        // Plan selection buttons
        document.querySelectorAll('.plan-select-btn').forEach(button => {
            button.addEventListener('click', (e) => this.handlePlanSelection(e));
        });

        // Upgrade/downgrade buttons
        document.querySelectorAll('.upgrade-btn, .downgrade-btn').forEach(button => {
            button.addEventListener('click', (e) => this.handleSubscriptionChange(e));
        });

        // Business waitlist form
        const waitlistForm = document.getElementById('businessWaitlistForm');
        if (waitlistForm) {
            waitlistForm.addEventListener('submit', (e) => this.handleWaitlistSubmission(e));
        }
    }

    setupTooltips() {
        const tooltipTriggerList = [].slice.call(
            document.querySelectorAll('[data-bs-toggle="tooltip"]')
        );
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    handleBillingToggle(event) {
        this.billingCycle = event.target.checked ? 'yearly' : 'monthly';
        this.updatePriceDisplay();

        // Show/hide savings badges
        document.querySelectorAll('.savings-badge').forEach(badge => {
            badge.style.display = this.billingCycle === 'yearly' ? 'inline-block' : 'none';
        });
    }

    updatePriceDisplay() {
        document.querySelectorAll('.pricing-display').forEach(display => {
            const tier = display.dataset.tier;
            const prices = this.getPrices(tier);
            const price = this.billingCycle === 'yearly' ? prices.yearly : prices.monthly;
            const interval = this.billingCycle === 'yearly' ? '/year' : '/mo';

            display.textContent = price === 'Free' ? 'Free' : `${price}${interval}`;
        });
    }

    async handlePlanSelection(event) {
        const button = event.currentTarget;
        const tier = button.dataset.tier;
        const currentTier = document.querySelector('meta[name="user-subscription-tier"]')?.content;

        try {
            if (tier === currentTier) {
                this.showToast('Info', 'You are already subscribed to this plan', 'info');
                return;
            }

            if (tier === 'business') {
                this.showBusinessWaitlist();
                return;
            }

            button.disabled = true;
            button.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Processing...';

            if (tier === 'solo_backpacker') {
                await this.handleDowngrade();
            } else {
                await this.createCheckoutSession(tier);
            }
        } catch (error) {
            console.error('Plan selection error:', error);
            this.showToast('Error', 'Failed to process plan selection', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = this.getButtonText(tier);
        }
    }

    async createCheckoutSession(tier) {
        try {
            const response = await fetch('/api/create-checkout-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    tier: tier,
                    billingCycle: this.billingCycle,
                    priceId: this.priceIds[tier][this.billingCycle]
                })
            });

            if (!response.ok) {
                throw new Error('Failed to create checkout session');
            }

            const session = await response.json();
            await this.stripe.redirectToCheckout({
                sessionId: session.id
            });
        } catch (error) {
            console.error('Checkout error:', error);
            throw new Error('Failed to initiate checkout');
        }
    }

    async handleDowngrade() {
        try {
            const response = await fetch('/api/downgrade-subscription', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error('Failed to process downgrade');
            }

            window.location.reload();
        } catch (error) {
            console.error('Downgrade error:', error);
            throw new Error('Failed to process downgrade');
        }
    }

    showBusinessWaitlist() {
        const modal = new bootstrap.Modal(document.getElementById('businessWaitlistModal'));
        modal.show();
    }

    async handleWaitlistSubmission(event) {
        event.preventDefault();
        const form = event.target;
        const submitButton = form.querySelector('button[type="submit"]');

        try {
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Submitting...';

            const formData = new FormData(form);
            const response = await fetch('/api/business-waitlist', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Failed to join waitlist');
            }

            this.showToast('Success', 'Successfully joined the business waitlist!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('businessWaitlistModal')).hide();
            form.reset();
        } catch (error) {
            console.error('Waitlist error:', error);
            this.showToast('Error', 'Failed to join waitlist', 'error');
        } finally {
            submitButton.disabled = false;
            submitButton.innerHTML = 'Submit';
        }
    }

    getPrices(tier) {
        return {
            solo_backpacker: {
                monthly: 'Free',
                yearly: 'Free'
            },
            tandem_trekker: {
                monthly: '$4.99',
                yearly: '$49.90'
            },
            gold_wanderer: {
                monthly: '$14.99',
                yearly: '$149.90'
            },
            business: {
                monthly: 'Custom',
                yearly: 'Custom'
            }
        }[tier] || { monthly: 'Custom', yearly: 'Custom' };
    }

    getButtonText(tier) {
        const currentTier = document.querySelector('meta[name="user-subscription-tier"]')?.content;

        if (tier === currentTier) {
            return 'Current Plan';
        }

        if (tier === 'business') {
            return 'Join Waitlist';
        }

        if (tier === 'solo_backpacker') {
            return 'Downgrade to Free';
        }

        return currentTier === 'solo_backpacker' ? 'Upgrade Now' : 'Switch Plan';
    }

    showToast(title, message, type = 'info') {
        if (typeof window.showToast === 'function') {
            window.showToast(title, message, type);
        } else {
            const toastContainer = document.querySelector('.toast-container') || 
                document.createElement('div');

            if (!document.body.contains(toastContainer)) {
                toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
                document.body.appendChild(toastContainer);
            }

            const toastElement = document.createElement('div');
            toastElement.className = `toast ${type} align-items-center border-0`;
            toastElement.innerHTML = `
                <div class="toast-header bg-${type} text-white">
                    <strong class="me-auto">${title}</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">${message}</div>
            `;

            toastContainer.appendChild(toastElement);
            const toast = new bootstrap.Toast(toastElement, {
                autohide: true,
                delay: 5000
            });
            toast.show();
        }
    }
}

// Initialize the pricing manager when the document is ready
document.addEventListener('DOMContentLoaded', () => {
    window.pricingManager = new PricingManager();
});

// Export for module usage if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PricingManager;
}