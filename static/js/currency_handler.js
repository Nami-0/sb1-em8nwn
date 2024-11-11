// currency_handler.js
class CurrencyHandler {
    constructor() {
        // Cache settings
        this.CACHE_EXPIRY = 3600; // 1 hour in seconds
        this.CACHE_PREFIX = 'currency:';
        this.RATE_CACHE_PREFIX = 'exchange_rate:';

        // Default currency
        this.defaultCurrency = 'MYR';

        // Initialize currency formatter
        this.formatter = new Intl.NumberFormat('en-MY', {
            style: 'currency',
            currency: this.defaultCurrency
        });

        // Rate update timeout
        this.updateTimeout = null;

        // Initialize cache system
        this.initializeCache();
    }

    // Initialize the cache system
    async initializeCache() {
        try {
            // Try to get cached rates from Redis first
            const cachedRates = await this.getRatesFromRedis();
            if (cachedRates) {
                console.log('Loaded rates from Redis cache');
                return;
            }

            // If no Redis cache, update rates
            await this.updateRates();
        } catch (error) {
            console.warn('Cache initialization failed:', error);
        }
    }

    // Get rates from Redis cache
    async getRatesFromRedis() {
        try {
            const response = await fetch('/api/redis/rates', {
                headers: {
                    'Cache-Control': 'no-cache',
                    'X-Cache-Check': 'true'
                }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch from Redis');
            }

            const data = await response.json();
            if (data && data.rates) {
                return data.rates;
            }
        } catch (error) {
            console.warn('Redis cache miss:', error);
        }
        return null;
    }

    // Cache rates in Redis
    async cacheRatesInRedis(rates) {
        try {
            const response = await fetch('/api/redis/rates', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Cache-Store': 'true'
                },
                body: JSON.stringify({
                    rates,
                    expiry: this.CACHE_EXPIRY
                })
            });

            if (!response.ok) {
                throw new Error('Failed to cache in Redis');
            }

            console.log('Successfully cached rates in Redis');
        } catch (error) {
            console.warn('Failed to cache rates in Redis:', error);
        }
    }

    // Format amount in specified currency
    formatAmount(amount, currency = this.defaultCurrency) {
        try {
            const formatter = new Intl.NumberFormat('en-MY', {
                style: 'currency',
                currency: currency
            });
            return formatter.format(amount);
        } catch (error) {
            console.error('Currency formatting error:', error);
            return `${amount} ${currency}`;
        }
    }

    // Update exchange rates with Redis caching
    async updateRates() {
        try {
            if (this.updateTimeout) {
                clearTimeout(this.updateTimeout);
            }

            // Try to get cached rates from Redis
            const cachedRates = await this.getRatesFromRedis();
            if (cachedRates) {
                return this.processRates(cachedRates);
            }

            // Fetch new rates if cache miss
            const rates = await this.fetchExchangeRates();
            if (!rates) {
                throw new Error('No rates received from API');
            }

            // Cache in Redis
            await this.cacheRatesInRedis(rates);

            // Process and store rates
            this.processRates(rates);

            // Schedule next update
            this.updateTimeout = setTimeout(
                () => this.updateRates(),
                this.CACHE_EXPIRY * 1000
            );

        } catch (error) {
            console.error('Failed to update exchange rates:', error);
        }
    }

    // Process and store rates
    processRates(rates) {
        // Store rates with cache timestamp
        localStorage.setItem(this.CACHE_PREFIX + 'rates', JSON.stringify({
            rates,
            timestamp: Date.now()
        }));

        // Emit rate update event
        window.dispatchEvent(new CustomEvent('ratesUpdated', { detail: rates }));
    }

    // Fetch exchange rates from API
    async fetchExchangeRates() {
        try {
            const response = await fetch('/api/exchange-rates');
            if (!response.ok) {
                throw new Error('Exchange rate API request failed');
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching exchange rates:', error);
            return null;
        }
    }

    // Get single rate from Redis
    async getRateFromRedis(fromCurrency, toCurrency) {
        const key = `${this.RATE_CACHE_PREFIX}${fromCurrency}_${toCurrency}`;
        try {
            const response = await fetch(`/api/redis/rate/${key}`);
            if (response.ok) {
                const data = await response.json();
                return data.rate;
            }
        } catch (error) {
            console.warn('Redis rate cache miss:', error);
        }
        return null;
    }

    // Cache single rate in Redis
    async cacheRateInRedis(fromCurrency, toCurrency, rate) {
        const key = `${this.RATE_CACHE_PREFIX}${fromCurrency}_${toCurrency}`;
        try {
            await fetch('/api/redis/rate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    key,
                    rate,
                    expiry: this.CACHE_EXPIRY
                })
            });
        } catch (error) {
            console.warn('Failed to cache rate in Redis:', error);
        }
    }

    // Convert amount between currencies with Redis caching
    async convertAmount(amount, fromCurrency, toCurrency) {
        try {
            if (fromCurrency === toCurrency) {
                return amount;
            }

            // Try to get rate from Redis first
            const cachedRate = await this.getRateFromRedis(fromCurrency, toCurrency);
            if (cachedRate !== null) {
                return amount * cachedRate;
            }

            // If no cached rate, calculate and cache
            const rate = await this.calculateRate(fromCurrency, toCurrency);
            await this.cacheRateInRedis(fromCurrency, toCurrency, rate);

            return amount * rate;
        } catch (error) {
            console.error('Currency conversion error:', error);
            return amount;
        }
    }

    // Calculate exchange rate between currencies
    async calculateRate(fromCurrency, toCurrency) {
        // Get rates from cache or update
        const cachedData = localStorage.getItem(this.CACHE_PREFIX + 'rates');
        let rates;

        if (cachedData) {
            const { rates: cachedRates, timestamp } = JSON.parse(cachedData);
            if (Date.now() - timestamp < this.CACHE_EXPIRY * 1000) {
                rates = cachedRates;
            }
        }

        if (!rates) {
            await this.updateRates();
            const newCachedData = localStorage.getItem(this.CACHE_PREFIX + 'rates');
            if (newCachedData) {
                rates = JSON.parse(newCachedData).rates;
            }
        }

        if (!rates) {
            throw new Error('No exchange rates available');
        }

        return rates[toCurrency] / rates[fromCurrency];
    }

    // Update UI elements with converted currency
    async updateUIElements(elements, fromCurrency, toCurrency) {
        for (const element of elements) {
            try {
                const amount = parseFloat(element.dataset.amount);
                if (isNaN(amount)) continue;

                const convertedAmount = await this.convertAmount(amount, fromCurrency, toCurrency);
                element.textContent = this.formatAmount(convertedAmount, toCurrency);

                // Update data attributes
                element.dataset.currency = toCurrency;
                element.dataset.amount = amount.toString();
            } catch (error) {
                console.error('Error updating element:', error);
            }
        }
    }

    // Initialize currency selectors
    initializeSelectors() {
        document.querySelectorAll('select[data-currency-selector]').forEach(selector => {
            selector.addEventListener('change', async (event) => {
                const newCurrency = event.target.value;
                const oldCurrency = event.target.dataset.currentCurrency;

                // Get all elements that need updating
                const elements = document.querySelectorAll('[data-currency]');
                await this.updateUIElements(elements, oldCurrency, newCurrency);

                // Update current currency
                event.target.dataset.currentCurrency = newCurrency;

                // Emit change event
                selector.dispatchEvent(new CustomEvent('currencyChanged', {
                    detail: { oldCurrency, newCurrency }
                }));
            });
        });
    }

    // Static utility methods
    static getSymbolPlacement(currency) {
        const postfixCurrencies = ['JPY', 'KRW', 'VND'];
        return postfixCurrencies.includes(currency) ? 'after' : 'before';
    }
}

// Export for module use
export default CurrencyHandler;

// Initialize if using directly in browser
if (typeof window !== 'undefined') {
    window.currencyHandler = new CurrencyHandler();
    window.currencyHandler.initializeSelectors();
}