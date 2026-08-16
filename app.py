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

# Load pickle artifacts safely
try:
    popular_df = load_pickle('popular.pkl')
    pt = load_pickle('pt.pkl')
    books_file = 'books.pkl' if os.path.exists(os.path.join(BASE_DIR, 'books.pkl')) else 'book.pkl'
    books = load_pickle(books_file)
    similarity_scores = load_pickle('similarity_scores.pkl')
    print("All pickle models loaded successfully.")
except Exception as e:
    print(f"CRITICAL ERROR loading pickle files: {e}", file=sys.stderr)
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
    if 'Image-URL-L' in popular_df.columns:
        raw_imgs = popular_df['Image-URL-L'].values
    elif 'Image-URL-M' in popular_df.columns:
        raw_imgs = popular_df['Image-URL-M'].values
    else:
        raw_imgs = [''] * len(popular_df)
        
    images = [get_hd_image(img) for img in raw_imgs]
    
    return render_template(
        'index.html',
        book_name=list(popular_df['Book-Title'].values),
        author=list(popular_df['Book-Author'].values),
        image=images,
        votes=list(popular_df['num_ratings'].values),
        rating=[round(float(r), 2) for r in popular_df['avg_rating'].values]
    )

@app.route('/recommend')
def recommend_ui():
    return render_template('recommend.html')

@app.route('/api/suggest')
def suggest():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])
    
    matches = [title for title in pt.index if query.lower() in title.lower()]
    return jsonify(matches[:10])

@app.route('/recommend_books', methods=['POST'])
def recommend():
    user_input = request.form.get('user_input', '').strip()
    
    if not user_input:
        return render_template('recommend.html', error="Please enter a book title.")
    
    matched_title = None
    if user_input in pt.index:
        matched_title = user_input
    else:
        possible_matches = [t for t in pt.index if user_input.lower() in t.lower()]
        if possible_matches:
            matched_title = possible_matches[0]
            
    if not matched_title:
        return render_template(
            'recommend.html', 
            user_input=user_input,
            error=f"Sorry, '{user_input}' was not found in our rating database. Try selecting from the search suggestions!"
        )

    try:
        index = np.where(pt.index == matched_title)[0][0]
        similar_items = sorted(
            list(enumerate(similarity_scores[index])), 
            key=lambda x: x[1], 
            reverse=True
        )[1:6]

        data = []
        for i in similar_items:
            item = []
            temp_df = books[books['Book-Title'] == pt.index[i[0]]]
            if temp_df.empty:
                continue
                
            book_row = temp_df.drop_duplicates('Book-Title').iloc[0]
            
            title = book_row['Book-Title']
            author = book_row['Book-Author']
            
            raw_image_url = book_row.get('Image-URL-L', book_row.get('Image-URL-M', ''))
            image_url = get_hd_image(raw_image_url)
            
            match_percentage = round(float(i[1]) * 100, 1)

            item.extend([title, author, image_url, match_percentage])
            data.append(item)

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
