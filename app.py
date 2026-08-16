from flask import Flask, render_template, request, jsonify
import pickle
import numpy as np
import os
import sys

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_pickle(filename):
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Pickle file not found: {path}")
    with open(path, 'rb') as f:
        return pickle.load(f)

# Load native Python models safely
try:
    popular_data = load_pickle('popular.pkl')
    pt_titles = load_pickle('pt.pkl')
    books_file = 'books.pkl' if os.path.exists(os.path.join(BASE_DIR, 'books.pkl')) else 'book.pkl'
    books_dict = load_pickle(books_file)
    similarity_scores = load_pickle('similarity_scores.pkl')
    print("Native Python models loaded successfully.")
except Exception as e:
    print(f"CRITICAL ERROR loading model files: {e}", file=sys.stderr)
    raise e

def get_hd_image(url):
    """Converts low/medium res Amazon image URLs to High-Res Large URLs and ensures HTTPS protocol."""
    if not isinstance(url, str) or not url:
        return 'https://images.unsplash.com/photo-1543002588-bfa74002ed7e?auto=format&fit=crop&w=600&q=80'
    
    url = url.replace('http://', 'https://')
    if '.MZZZZZZZ.jpg' in url:
        url = url.replace('.MZZZZZZZ.jpg', '.LZZZZZZZ.jpg')
    elif '.SZZZZZZZ.jpg' in url:
        url = url.replace('.SZZZZZZZ.jpg', '.LZZZZZZZ.jpg')
        
    return url

@app.route('/')
def index():
    raw_imgs = popular_data.get('image', [])
    images = [get_hd_image(img) for img in raw_imgs]
    
    return render_template(
        'index.html',
        book_name=popular_data.get('book_name', []),
        author=popular_data.get('author', []),
        image=images,
        votes=popular_data.get('votes', []),
        rating=[round(float(r), 2) for r in popular_data.get('rating', [])]
    )

@app.route('/recommend')
def recommend_ui():
    return render_template('recommend.html')

@app.route('/api/suggest')
def suggest():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])
    
    matches = [title for title in pt_titles if query.lower() in title.lower()]
    return jsonify(matches[:10])

@app.route('/recommend_books', methods=['POST'])
def recommend():
    user_input = request.form.get('user_input', '').strip()
    
    if not user_input:
        return render_template('recommend.html', error="Please enter a book title.")
    
    matched_title = None
    if user_input in pt_titles:
        matched_title = user_input
    else:
        possible_matches = [t for t in pt_titles if user_input.lower() in t.lower()]
        if possible_matches:
            matched_title = possible_matches[0]
            
    if not matched_title:
        return render_template(
            'recommend.html', 
            user_input=user_input,
            error=f"Sorry, '{user_input}' was not found in our rating database. Try selecting from the search suggestions!"
        )

    try:
        index = pt_titles.index(matched_title)
        similar_items = sorted(
            list(enumerate(similarity_scores[index])), 
            key=lambda x: x[1], 
            reverse=True
        )[1:6]

        data = []
        for i in similar_items:
            similar_book_title = pt_titles[i[0]]
            book_info = books_dict.get(similar_book_title)
            
            if not book_info:
                continue
                
            title = book_info.get('Book-Title', similar_book_title)
            author = book_info.get('Book-Author', 'Unknown Author')
            raw_image_url = book_info.get('Image-URL-L', book_info.get('Image-URL-M', ''))
            image_url = get_hd_image(raw_image_url)
            
            match_percentage = round(float(i[1]) * 100, 1)

            data.append([title, author, image_url, match_percentage])

        return render_template(
            'recommend.html', 
            data=data, 
            user_input=matched_title
        )
    except Exception as e:
        return render_template(
            'recommend.html', 
            user_input=user_input,
            error=f"An error occurred while generating recommendations: {str(e)}"
        )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
