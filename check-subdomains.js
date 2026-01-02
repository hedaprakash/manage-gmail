const fs = require('fs');
const criteria = JSON.parse(fs.readFileSync('criteria_unified.json', 'utf-8'));
const domains = Object.keys(criteria);

const suspicious = [];
for (const domain of domains) {
  const parts = domain.split('.');
  if (parts.length >= 3) {
    let parentDomain;
    const lastTwo = parts.slice(-2).join('.');
    // Handle country-code TLDs like .co.in, .co.uk
    if (lastTwo.match(/^(co|com|org|net|ac)\.(in|uk|au|nz|jp)$/)) {
      if (parts.length > 3) {
        parentDomain = parts.slice(-3).join('.');
      }
    } else {
      parentDomain = parts.slice(-2).join('.');
    }

    if (parentDomain && parentDomain !== domain) {
      const parentExists = domains.includes(parentDomain);
      suspicious.push({
        entry: domain,
        parent: parentDomain,
        exists: parentExists
      });
    }
  }
}

console.log(`Found ${suspicious.length} potential subdomain entries:\n`);
suspicious.forEach(s => {
  console.log(`  ${s.entry}`);
  console.log(`    -> parent: ${s.parent} (exists: ${s.exists ? 'YES' : 'NO'})`);
});
