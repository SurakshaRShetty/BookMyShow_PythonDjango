from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import timedelta
import stripe
from moviebooking import secret_key
from django.core.mail import send_mail
from .models import Movie, Seat, Booking
from django.db.models import Sum
from django.contrib.admin.views.decorators import staff_member_required



# ---------------- MOVIE LIST ----------------
def movie_list(request):
    genre = request.GET.get('genre')
    language = request.GET.get('language')

    movies = Movie.objects.all()

    if genre:
        movies = movies.filter(genre=genre)

    if language:
        movies = movies.filter(language=language)

    return render(request, 'booking/movie_list.html', {
        'movies': movies,
        'selected_genre': genre,
        'selected_language': language,
    })


# ---------------- MOVIE DETAIL ----------------
def movie_detail(request, id):
    movie = Movie.objects.get(id=id)
    seats = Seat.objects.filter(movie=movie)

    reserved_seat_ids = request.session.get('reserved_seat_ids', [])

    # 🔥 RELEASE EXPIRED SEATS + CLEAN SESSION
    for seat in seats:
        if seat.reserved_until is not None and timezone.now() > seat.reserved_until:

            seat.is_booked = False
            seat.reserved_until = None
            seat.save()

            if seat.id in reserved_seat_ids:
                reserved_seat_ids.remove(seat.id)

    request.session['reserved_seat_ids'] = reserved_seat_ids

    seat_price = 200
    total_price = len(reserved_seat_ids) * seat_price

    return render(request, 'booking/movie_detail.html', {
        'movie': movie,
        'seats': seats,
        'reserved_seat_ids': reserved_seat_ids,
        'total_price': total_price,
    })


# ---------------- RESERVE / UNRESERVE SEAT ----------------
def reserve_seat(request, seat_id):
    # 🔥 GLOBAL EXPIRY CHECK
    Seat.objects.filter(
        reserved_until__isnull=False,
        reserved_until__lt=timezone.now()
    ).update(
        is_booked=False,
        reserved_until=None
    )

    seat = Seat.objects.get(id=seat_id)
    reserved_seat_ids = request.session.get('reserved_seat_ids', [])

    # 🔁 UNSELECT SEAT
    if seat.id in reserved_seat_ids:
        seat.is_booked = False
        seat.reserved_until = None
        seat.save()

        reserved_seat_ids.remove(seat.id)
        request.session['reserved_seat_ids'] = reserved_seat_ids

        return redirect('movie_detail', id=seat.movie.id)

    # ✅ SELECT SEAT
    if not seat.is_booked:
        seat.is_booked = True
        seat.reserved_until = timezone.now() + timedelta(minutes=5)
        seat.save()

        reserved_seat_ids.append(seat.id)
        request.session['reserved_seat_ids'] = reserved_seat_ids

    return redirect('movie_detail', id=seat.movie.id)


# ---------------- STRIPE PAYMENT ----------------
stripe.api_key = secret_key.STRIPE_SECRET_KEY

def create_checkout_session(request, movie_id):
    movie = Movie.objects.get(id=movie_id)
    seat_count = len(request.session.get('reserved_seat_ids', []))

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'inr',
                'product_data': {'name': movie.title},
                'unit_amount': 20000,  # ₹200
            },
            'quantity': seat_count,
        }],
        mode='payment',
        success_url='http://127.0.0.1:8000/payment-success/',
        cancel_url='http://127.0.0.1:8000/payment-cancel/',
    )

    return redirect(session.url)


# ---------------- PAYMENT SUCCESS ----------------
def payment_success(request):
    reserved_seat_ids = request.session.get('reserved_seat_ids', [])

    seats = Seat.objects.filter(id__in=reserved_seat_ids)
    movie = seats.first().movie if seats.exists() else None

    seat_numbers = ", ".join([seat.seat_number for seat in seats])
    total_price = seats.count() * 200
    booking_time = timezone.now().strftime("%d %b %Y, %I:%M %p")

    # 🔥 SAVE BOOKING FOR ADMIN ANALYTICS
    if movie:
        Booking.objects.create(
            movie=movie,
            seats_count=seats.count(),
            total_price=total_price
        )

    # 📧 EMAIL CONFIRMATION
    subject = "🎟 Movie Ticket Confirmation"
    message = f"""
Hello,

Your movie ticket has been successfully booked!

🎬 Movie: {movie.title if movie else 'N/A'}
💺 Seats: {seat_numbers}
💰 Amount Paid: ₹{total_price}
🕒 Booking Time: {booking_time}

Enjoy your show 🍿
Thank you for booking with us!
"""

    send_mail(
        subject,
        message,
        'noreply@moviebooking.com',
        ['testuser@example.com'],
        fail_silently=False,
    )

    # 🔒 MARK SEATS AS PERMANENTLY BOOKED
    for seat in seats:
        seat.is_booked = True
        seat.reserved_until = None
        seat.save()

    # Clear session
    request.session.pop('reserved_seat_ids', None)

    return render(request, 'booking/payment_success.html')




# ---------------- PAYMENT CANCEL ----------------
def payment_cancel(request):
    reserved_seat_ids = request.session.get('reserved_seat_ids', [])

    Seat.objects.filter(id__in=reserved_seat_ids).update(
        is_booked=False,
        reserved_until=None
    )

    request.session.pop('reserved_seat_ids', None)

    return render(request, 'booking/payment_cancel.html')



@staff_member_required
def admin_dashboard(request):
    # 💰 TOTAL REVENUE
    total_revenue = Booking.objects.aggregate(
        total=Sum('total_price')
    )['total'] or 0

    # 🎬 MOVIE-WISE STATS
    movie_stats = Booking.objects.values(
        'movie__title'
    ).annotate(
        seats_booked=Sum('seats_count'),
        revenue=Sum('total_price')
    ).order_by('-seats_booked')

    # 🔥 MOST POPULAR MOVIE
    most_popular_movie = movie_stats.first()

    return render(request, 'booking/admin_dashboard.html', {
        'total_revenue': total_revenue,
        'movie_stats': movie_stats,
        'most_popular_movie': most_popular_movie,
    })
