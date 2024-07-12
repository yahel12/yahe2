if [ -z $UPSTREAM_REPO ]
then
  echo "Cloning main Repository"
  git clone https://github.com/Godstime5/hey_tessgit /hey_tess
else
  echo "Cloning Custom Repo from $UPSTREAM_REPO "
  git clone $UPSTREAM_REPO /hey_tess
fi
cd /hey_tess
pip3 install -U -r requirements.txt
echo "Starting hey_tess...."
python3 bot.py
