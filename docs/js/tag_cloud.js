// add as much as you want
const tags = [
    { text: 'JavaScript', size: 5, count: 150 },
    { text: 'Python', size: 5, count: 142 },
    { text: 'React', size: 4, count: 125 },
    { text: 'CSS', size: 4, count: 115 },
    { text: 'HTML', size: 4, count: 110 },
    { text: 'Node.js', size: 3, count: 95 },
    { text: 'TypeScript', size: 3, count: 88 },
    { text: 'Vue.js', size: 3, count: 82 },
    { text: 'Angular', size: 3, count: 78 },
    { text: 'Docker', size: 2, count: 65 },
    { text: 'MongoDB', size: 2, count: 60 },
    { text: 'SQL', size: 2, count: 55 },
    { text: 'AWS', size: 2, count: 50 },
    { text: 'Git', size: 1, count: 45 },
    { text: 'Redux', size: 1, count: 40 },
    { text: 'GraphQL', size: 1, count: 35 },
];

const tagCloud = document.querySelector('.tag-cloud');

const shuffledTags = [...tags].sort(() => Math.random() - 0.5);

shuffledTags.forEach((tag, index) => {
    const tagElement = document.createElement('span');
    tagElement.className = `tag size-${tag.size} color-${(index % 5) + 1}`;
    tagElement.innerHTML = `${tag.text}<span class="tag-count">${tag.count}</span>`;

    tagElement.addEventListener('click', function () {
        this.classList.add('selected');
        setTimeout(() => this.classList.remove('selected'), 300);
    });

    tagCloud.appendChild(tagElement);
});

document.querySelectorAll('.tag').forEach(tag => {
    tag.style.transform = `rotate(${(Math.random() * 6) - 3}deg)`;
});
