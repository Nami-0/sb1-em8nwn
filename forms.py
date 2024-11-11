from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, BooleanField, DateField, SelectField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, NumberRange, Length, ValidationError, Email, Regexp
from currency_data import CURRENCY_DATA, get_currency_display_name


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ProfileForm(FlaskForm):
    username = StringField('Username',
                         validators=[DataRequired(),
                                   Length(min=3, max=64)])
    phone_number = StringField(
        'Phone Number',
        validators=[
            DataRequired(),
            Regexp(r'^\+?[\d\s-]+$',
                  message="Please enter a valid phone number")
        ])
    preferred_currency = SelectField(
        'Preferred Currency',
        choices=[(code, get_currency_display_name(code)) for code in CURRENCY_DATA.keys()],
        default='MYR'
    )


class ItineraryForm(FlaskForm):
    citizenship = SelectField('Citizenship',
                            choices=[('malaysia', 'Malaysia'),
                                   ('singapore', 'Singapore'),
                                   ('indonesia', 'Indonesia'),
                                   ('thailand', 'Thailand'),
                                   ('vietnam', 'Vietnam'),
                                   ('philippines', 'Philippines'),
                                   ('china', 'China'), ('japan', 'Japan'),
                                   ('south_korea', 'South Korea'),
                                   ('india', 'India'),
                                   ('australia', 'Australia'),
                                   ('new_zealand', 'New Zealand'),
                                   ('united_states', 'United States'),
                                   ('united_kingdom', 'United Kingdom'),
                                   ('canada', 'Canada'),
                                   ('other', 'Other')],
                            validators=[DataRequired()])

    destinations = SelectField('Destination',
                             choices=[('surprise_me', 'Surprise Me!'),
                                    ('australia', 'Australia'),
                                    ('bangladesh', 'Bangladesh'),
                                    ('brazil', 'Brazil'),
                                    ('canada', 'Canada'),
                                    ('china', 'China'), ('egypt', 'Egypt'),
                                    ('france', 'France'),
                                    ('germany', 'Germany'),
                                    ('india', 'India'),
                                    ('indonesia', 'Indonesia'),
                                    ('italy', 'Italy'), ('japan', 'Japan'),
                                    ('malaysia', 'Malaysia'),
                                    ('mexico', 'Mexico'),
                                    ('netherlands', 'Netherlands'),
                                    ('new_zealand', 'New Zealand'),
                                    ('singapore', 'Singapore'),
                                    ('south_korea', 'South Korea'),
                                    ('spain', 'Spain'),
                                    ('thailand', 'Thailand'),
                                    ('united_arab_emirates',
                                     'United Arab Emirates'),
                                    ('united_kingdom', 'United Kingdom'),
                                    ('united_states', 'United States'),
                                    ('vietnam', 'Vietnam')],
                             validators=[DataRequired()])

    currency = SelectField(
        'Budget Currency',
        choices=[(code, get_currency_display_name(code)) for code in CURRENCY_DATA.keys()],
        validators=[DataRequired()],
        default='MYR',
        description='Select the currency for your budget'
    )

    specific_locations = StringField('Specific Places/Landmarks')

    travel_focus = MultiCheckboxField('Travel Focus',
                                    choices=[
                                        ('scenery', 'Scenery'),
                                        ('food_hunting', 'Food Hunting'),
                                        ('cultural', 'Cultural Experience'),
                                        ('adventure', 'Adventure'),
                                        ('relaxation', 'Relaxation'),
                                        ('shopping', 'Shopping'),
                                        ('historical', 'Historical Sites'),
                                        ('nature', 'Nature & Wildlife')
                                    ])

    budget = FloatField('Budget',
                       validators=[DataRequired(),
                                 NumberRange(min=0)])

    include_flights = BooleanField('Include Flights in Budget', default=True)
    include_accommodation = BooleanField('Include Accommodation in Budget',
                                       default=True)

    # New age group fields replacing num_people
    num_adults = IntegerField('Adults (18 years and above)',
                            validators=[DataRequired(),
                                      NumberRange(min=0)],
                            default=1)
    num_youth = IntegerField('Youth (12-17 years)',
                           validators=[DataRequired(),
                                     NumberRange(min=0)],
                           default=0)
    num_children = IntegerField(
        'Children (2-11 years)',
        validators=[DataRequired(), NumberRange(min=0)],
        default=0)
    num_infants = IntegerField('Infants (under 2 years)',
                             validators=[DataRequired(),
                                       NumberRange(min=0)],
                             default=0)

    accommodation_location = StringField('Accommodation Location',
                                       validators=[DataRequired()])
    accommodation_name = StringField('Hotel/Accommodation Name',
                                   validators=[DataRequired()])

    need_guide = BooleanField(
        'Need a Travel Buddy?',
        description=
        'Connect with a local Travel Buddy who will guide and assist you throughout your journey (MYR 500 per day)'
    )
    halal_food = BooleanField('Halal Food Required')
    vegan_food = BooleanField('Vegan Food Required')
    wheelchair_accessible = BooleanField(
        'Wheelchair Accessibility Required',
        description=
        'We will prioritize wheelchair-accessible locations and provide accessibility information in your itinerary'
    )

    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])

    def validate_infants(self, field):
        if (field.data > 0
                or self.num_children.data > 0) and self.num_adults.data < 1:
            raise ValidationError(
                'At least one adult is required when traveling with children or infants'
            )

    def validate(self, extra_validators=None):
        if not super().validate():
            return False

        total_travelers = (self.num_adults.data + self.num_youth.data +
                         self.num_children.data + self.num_infants.data)

        if total_travelers < 1:
            self.num_adults.errors.append('At least one traveler is required')
            return False

        if total_travelers > 10:
            self.num_adults.errors.append(
                'Maximum 10 travelers allowed per itinerary')
            return False

        return True

    def get_budget_display(self):
        """Get the budget amount with currency display"""
        from currency_data import format_currency
        return format_currency(self.budget.data, self.currency.data)