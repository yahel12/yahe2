if [ -z $UPSTREAM_REPO ]
then
  echo "Cloning main Repository"
  git clone https://github.com/blealex/DQ.git /DQ
else
  echo "Cloning Custom Repo from $UPSTREAM_REPO "
  git clone $UPSTREAM_REPO /DQ
fi
cd /DQ
pip3 install -U -r requirements.txt
echo "Starting DQ...."
python3 bot.py
